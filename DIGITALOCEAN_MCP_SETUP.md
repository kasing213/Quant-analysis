# DigitalOcean MCP Server Setup Guide

## Current Status
✅ Configuration template updated in `.mcp.json.template`
⏳ Waiting for DigitalOcean API token

## Prerequisites Met
- ✅ Node.js v18+ (you have npm 10.9.2)
- ✅ npm v8+
- ⏳ DigitalOcean API token (to be obtained)

## Next Steps

### 1. Get Your DigitalOcean API Token

1. Log in to [DigitalOcean](https://cloud.digitalocean.com/)
2. Go to **API** → **Tokens/Keys**
3. Click **Generate New Token**
4. Give it a name (e.g., "MCP Server Token")
5. Select appropriate scopes:
   - ✅ Read access
   - ✅ Write access (if you want to manage resources)
6. Copy the token immediately (you can only see it once!)

### 2. Update Your Configuration

Copy `.mcp.json.template` to your actual MCP config file and update the token:

```bash
# The config location depends on your Claude setup:
# - Claude Desktop: ~/.claude/claude_desktop_config.json
# - Claude Code: .mcp.json in your project
```

Replace `YOUR_DIGITALOCEAN_API_TOKEN_HERE` with your actual token.

### 3. Test the Setup

```bash
# Test if the MCP server works
npx @digitalocean/mcp --services apps
```

### 4. Restart Claude

Restart Claude Desktop or Claude Code to load the new MCP server.

## Configured Services

The configuration includes these DigitalOcean services:
- **apps**: App Platform applications and deployments
- **databases**: Managed databases (Postgres, MySQL, Redis)
- **droplets**: Virtual machine management

## Additional Services Available

You can add more services by modifying the `--services` argument:

| Service | Description |
|---------|-------------|
| `accounts` | Account, billing, SSH key management |
| `networking` | Domains, DNS, certificates, firewalls, load balancers |
| `spaces` | S3-compatible object storage |
| `insights` | Resource monitoring and alerts |
| `doks` | Kubernetes cluster management |
| `marketplace` | Marketplace application discovery |

Example to add more services:
```json
"args": ["-y", "@digitalocean/mcp", "--services", "apps,databases,droplets,networking,spaces"]
```

## Security Notes

⚠️ **IMPORTANT:**
- Never commit `.mcp.json` with real tokens to git!
- Keep `.mcp.json.template` with placeholder values
- Add `.mcp.json` to your `.gitignore`

## What You Can Do Once Set Up

With the DigitalOcean MCP server, you'll be able to:
- Deploy applications from GitHub to DigitalOcean App Platform
- Manage database clusters
- Create and manage droplets (VMs)
- Monitor resource usage
- Manage domains and DNS records
- And more through natural language commands in Claude!

## Troubleshooting

### Authentication Errors
- Verify your API token is correct
- Check token hasn't expired
- Ensure token has appropriate scopes

### Connection Issues
- Check your internet connection
- Verify DigitalOcean services are operational
- Check MCP server logs in Claude's developer tools

### Service Not Available
- Some services may not be available in all regions
- Check DigitalOcean's regional availability

## Example Usage

Once configured, you can ask Claude things like:
- "List all my DigitalOcean apps"
- "Deploy my app from GitHub to DigitalOcean"
- "Show me my database clusters"
- "Create a new droplet with 2GB RAM"
- "Check the logs for my app"

## Documentation Links

- [DigitalOcean MCP Server GitHub](https://github.com/digitalocean-labs/mcp-digitalocean)
- [Official Documentation](https://docs.digitalocean.com/products/app-platform/how-to/use-mcp/)
- [DigitalOcean API Documentation](https://docs.digitalocean.com/reference/api/)
