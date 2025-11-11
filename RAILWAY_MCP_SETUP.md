# Railway MCP Server Setup Guide

## Overview
Railway MCP server has been successfully built from source and configured for your project.

## What Was Fixed

### Platform Compatibility Issues on WSL2
- **Problem**: The npm package had Darwin (macOS) platform dependencies that failed on Linux
- **Solution**: Used `npm install --force` to bypass platform checks

### Missing Build Tool
- **Problem**: `tsdown` was not installed globally
- **Solution**: Installed `tsdown` globally with `npm install -g tsdown`

### Successful Build
- Built Railway MCP server from source
- Output located at: `/mnt/d/Tiktok-analyzing/railway-mcp-server/dist/index.js`

## Configuration

### .mcp.json Configuration (Windows/WSL2)
```json
{
  "railway": {
    "command": "node",
    "args": ["/mnt/d/Tiktok-analyzing/railway-mcp-server/dist/index.js"],
    "env": {
      "RAILWAY_TOKEN": "${Railway_Token}"
    }
  }
}
```

### Environment Variables (.env)
```bash
Railway_Token=bd1006ba-864a-412d-8155-cd4c538fbfcc
```

## Authentication

Before using Railway MCP, authenticate with Railway CLI:

```bash
railway login
```

Check authentication status:
```bash
railway whoami
```

## Available Railway MCP Tools

Once connected, the MCP server provides these tools:
- `check-railway-status` - Check Railway CLI installation and authentication
- `create-environment` - Create new Railway environment
- `create-project-and-link` - Create and link Railway project
- `deploy` - Deploy to Railway
- `deploy-template` - Deploy from template
- `generate-domain` - Generate Railway domain
- `get-logs` - Get deployment logs
- `link-environment` - Link to environment
- `link-service` - Link to service
- `list-deployments` - List deployments
- `list-projects` - List Railway projects
- `list-services` - List services
- `list-variables` - List environment variables
- `set-variables` - Set environment variables

## Usage in Claude Code

After reloading your IDE, the Railway MCP server will be available. You can:

1. **Check deployment logs**:
   ```
   Use Railway MCP to get logs for my deployment
   ```

2. **List projects**:
   ```
   Show me all my Railway projects
   ```

3. **Check deployment status**:
   ```
   What's the status of my Railway deployments?
   ```

## Troubleshooting

### Server Won't Start
- Ensure Railway CLI is installed: `railway --version`
- Authenticate: `railway login`
- Check token in .env file

### Permission Issues
- Make sure `dist/index.js` is executable: `chmod +x railway-mcp-server/dist/index.js`

### Node Version
- Requires Node.js 20.0.0 or higher
- Check version: `node --version`

## Windows vs WSL2 Path Differences

- **WSL2 path**: `/mnt/d/Tiktok-analyzing/railway-mcp-server/dist/index.js`
- **Windows path**: `D:\Tiktok-analyzing\railway-mcp-server\dist\index.js`

The .mcp.json uses WSL2 path since we're running in WSL environment.

## Additional Notes

- The Railway MCP server runs as a stdio-based MCP server
- It communicates via JSON-RPC over stdin/stdout
- All Railway CLI commands are available through the MCP interface
- Logs are streamed in real-time when requested
