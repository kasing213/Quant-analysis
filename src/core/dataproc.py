import numpy as np
import pandas as pd
import yfinance as yf

def load_prices(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)

    # Empty -> empty with proper index
    if df is None or df.empty:
        return pd.DataFrame({"price": []}, index=pd.DatetimeIndex([], name="Date"))

    # Handle both single- and multi-index columns from yfinance
    if isinstance(df.columns, pd.MultiIndex):
        # Expect something like ('Close', 'NVDA')
        if "Close" in df.columns.get_level_values(0):
            close = df["Close"]
            # If still 2-D (multiple tickers), pick the matching ticker or the first column
            if isinstance(close, pd.DataFrame):
                if ticker in getattr(close, "columns", []):
                    close = close[ticker]
                else:
                    close = close.iloc[:, 0]
        else:
            # Fallback: try to select 'Close' via xs
            try:
                close = df.xs("Close", axis=1, level=0)
                if isinstance(close, pd.DataFrame):
                    if ticker in getattr(close, "columns", []):
                        close = close[ticker]
                    else:
                        close = close.iloc[:, 0]
            except Exception:
                # Last resort: take the first column and hope it's close
                close = df.iloc[:, 0]
        out = pd.Series(close, name="price").to_frame()
    else:
        # Normal 1-level columns
        out = df[["Close"]].rename(columns={"Close": "price"}).dropna()

    # Normalize index/column names so Plotly sees plain "Date" and "price"
    out = out.dropna()
    out.index = pd.DatetimeIndex(out.index, name="Date")
    out.columns = ["price"]
    out.columns.name = None
    return out

def clean_prices(df: pd.DataFrame, clip_z: float = 6.0) -> pd.DataFrame:
    if df is None or df.empty or "price" not in df.columns:
        return pd.DataFrame(columns=["price"])

    df = df.copy().dropna()
    lr = np.log(df["price"]).diff()
    z = (lr - lr.mean()) / (lr.std(ddof=1) + 1e-12)

    keep = (z.abs() <= clip_z)
    # align to df.index; first row has NaN diff so keep it
    keep = keep.reindex(df.index, fill_value=False)
    if len(keep):
        keep.iloc[0] = True

    # 🔧 make absolutely sure it's 1-D boolean mask
    mask = keep.to_numpy(dtype=bool).reshape(-1)

    return df.iloc[mask].copy()

def compute_returns(price_df: pd.DataFrame) -> pd.DataFrame:
    # guard rails
    if price_df is None or price_df.empty or "price" not in price_df.columns:
        return pd.DataFrame({"ret": []}, index=pd.DatetimeIndex([], name="Date"))

    df = price_df.copy()
    df.index = pd.DatetimeIndex(df.index, name=df.index.name or "Date")

    # collapse to 1-D even if there are duplicate 'price' columns
    price_1d = np.asarray(df.loc[:, "price"]).reshape(-1).astype(float)

    s = pd.Series(price_1d, index=df.index, name="price")
    if len(s) < 2:
        return pd.DataFrame({"ret": []}, index=s.index[:0])

    r = s.pct_change().dropna()
    r.name = "ret"
    return r.to_frame()
