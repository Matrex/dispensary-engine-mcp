Features
✅ 
🖼️ 
⚡ Technical SEO: Page speed, HTTPS, schema markup detection
📊 Content Analysis: Word count, text-to-HTML ratio, content quality
📱 Social Media Tags: Open Graph and Twitter Cards optimization
🎯 SEO Scoring: Weighted scoring system with actionable recommendations
🔍 Multiple Analysis Types: Full analysis, quick checks, and meta tags focus
🚀 Async Operations: Non-blocking operations with proper timeout handling

Using Your Remote MCP Server
Option 1: Deploy Your Own Instance (1-Click)
Use Hostinger's 1-click deploy to get your own instance:

Click the "Deploy to Hostinger" button above
Hostinger automatically handles the Docker setup and deployment
Get your deployed URL (e.g., https://your-app.hstgr.cloud)
Add to your MCP client:
{
  "mcpServers": {
    "seo-checker": {
      "url": "https://your-app.hstgr.cloud/mcp",
      "description": "Professional SEO analysis and optimization recommendations"
    }
  }
}
Option 2: With FastMCP Development Tools
# Make sure your virtual environment is activated
fastmcp dev local-seo-checker.py
Option 3: Configure Local MCP Server
This MCP server works with Claude Desktop, Cursor, Windsurf, and other MCP-compatible applications.

Configuration Locations
Claude Desktop (Note: Remote MCP requires newer versions):

macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
Windows: %APPDATA%\Claude\claude_desktop_config.json
Cursor:

Settings > Tools & Integrations > MCP Tools
Or edit: ~/Library/Application Support/Cursor/cursor_desktop_config.json (macOS)
Windows: %APPDATA%\Cursor\cursor_desktop_config.json
Windsurf:

macOS: ~/Library/Application Support/Windsurf/windsurf_desktop_config.json
Windows: %APPDATA%\Windsurf\windsurf_desktop_config.json
For local development, add the following configuration to the appropriate file:

{
  "mcpServers": {
    "seo-checker": {
      "command": "/path/to/your/venv/bin/python",
      "args": ["/path/to/your/local-seo-checker.py"]
    }
  }
}
Important:

Replace paths with the actual paths to your virtual environment and SEO checker directory
Use local-seo-checker.py for local development (simpler configuration)
remote-seo-checker.py is configured for remote deployment with additional parameters
Installation (For Local Use)
Prerequisites
Python 3.8 or higher
pip package manager
Docker (for containerized deployment)
Setup
Clone the repository

git clone https://github.com/hostinger/selfhosted-mcp-server-template.git
cd selfhosted-mcp-server-template
Create and activate a virtual environment (recommended)

python -m venv venv
# On macOS/Linux
source venv/bin/activate
# On Windows
venv\Scripts\activate
Install dependencies

pip install -r requirements.txt
Deploy to Hostinger (1-Click) or Other Platforms
This MCP server can be deployed as a remote MCP server on various hosting platforms.

Hostinger (Recommended - 1-Click Deploy)
Hostinger provides seamless 1-click deployment for this MCP server template:

Click "Deploy to Hostinger" button at the top
Connect your GitHub account if not already connected
Select this repository from your repositories
Hostinger automatically:
Sets up the Docker environment
Installs all dependencies
Configures the correct port (8080)
Provides you with a live URL
Your MCP server is ready! Use the provided URL + /mcp
No manual configuration needed! Hostinger handles all the Docker Compose setup automatically.

Other Hosting Platforms (Manual Docker Deployment)
For other hosting platforms that support Docker:

Prerequisites
A hosting account (Hostinger, VPS, etc.)
Docker support on your hosting platform
Git repository with your code
Manual Docker Deployment (Other Platforms)
Connect to your server

ssh root@your-server-ip
Clone and deploy

# Install Docker if not present
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh

# Clone your repository
git clone https://github.com/hostinger/selfhosted-mcp-server-template.git
cd selfhosted-mcp-server-template

# Deploy with Docker Compose
docker-compose up -d --build
Configure firewall (if needed)

ufw allow 8080/tcp
Test your deployment

curl http://your-server-ip:8080
Using Your Deployed Server
Once deployed, configure your MCP client:

{
  "mcpServers": {
    "seo-checker": {
      "url": "http://your-server-domain:8080/mcp",
      "description": "Professional SEO analysis and optimization recommendations"
    }
  }
}
Available Tools
1. analyze_seo
Comprehensive SEO analysis of a webpage

Usage: "Analyze the SEO of example.com"

Features:

Title tag analysis (length, content, issues)
Meta description optimization
Header structure (H1-H6) analysis
Content quality assessment
Image alt text optimization
Technical SEO factors
Social media tags (Open Graph, Twitter Cards)
Overall SEO scoring with recommendations
2. seo_quick_check
Quick SEO health check

Usage: "Do a quick SEO check on github.com"

Features:

Rapid assessment of key SEO factors
Quick status indicators
Summary of critical issues
Basic performance metrics
3. seo_meta_tags_check
Focused analysis of meta tags and social media optimization

Usage: "Check the meta tags for linkedin.com"

Features:

Detailed meta tags analysis
Open Graph tags verification
Twitter Cards optimization
Canonical URL analysis
Robots meta tag inspection
Usage Examples
test-run
Comprehensive Analysis
"Analyze the SEO of my-website.com"

Quick Health Check
"Do a quick SEO check on competitor.com"

Meta Tags Focus
"Check the meta tags and social media optimization for blog-post-url.com"

Batch Analysis
"Compare the SEO of google.com, bing.com, and duckduckgo.com"

Understanding Results
SEO Score Grades
🏆 90-100 (EXCELLENT): Outstanding SEO optimization
🟢 80-89 (GOOD): Well-optimized with minor improvements needed
🟡 70-79 (FAIR): Decent SEO with several optimization opportunities
🟠 60-69 (NEEDS WORK): Significant SEO issues requiring attention
🔴 0-59 (POOR): Major SEO problems that need immediate action
Sample Output
🟢 SEO Analysis for example.com

🎯 OVERALL SEO SCORE: 85/100 (GOOD)

📄 TITLE TAG
• Content: "Example Domain - Official Website"
• Length: 35 characters
• Status: ✅ Good

📝 META DESCRIPTION
• Content: "This domain is for use in illustrative examples in documents..."
• Length: 145 characters
• Status: ✅ Good

🏗️ HEADER STRUCTURE
• H1 Tags: 1 ✅
• H2 Tags: 3
• H3 Tags: 2

📊 CONTENT ANALYSIS
• Word Count: 450 words
• Text-to-HTML Ratio: 25.3%
• Status: ✅ Good

🖼️ IMAGE OPTIMIZATION
• Total Images: 5
• With Alt Text: 4 (80%)
• Missing Alt Text: 1

⚡ TECHNICAL SEO
• HTTPS: ✅ Yes
• Load Time: 1250ms
• Page Size: 45.2 KB
• Schema Markup: ✅ Yes

💡 RECOMMENDATIONS (3)
• Add alt text to 1 images
• Consider adding more internal links
• Optimize images for faster loading
Troubleshooting
Debug Commands
# Check if server is running
curl http://your-server:8080

# View Docker logs
docker-compose logs -f seo-mcp-server

# Test locally
python remote-seo-checker.py

# Check port availability
netstat -tlnp | grep 8080
Development
Local Development
# Run in development mode
python local-seo-checker.py

# Test with MCP Inspector
npx @modelcontextprotocol/inspector
Contributing
Fork the repository
Create a feature branch
Make your changes
Test thoroughly
Submit a pull request
Adding New Analysis Features
The SEO checker is designed to be easily extensible. You can add new analysis methods by:

Adding methods to the SEOChecker class
Integrating them into the main analyze_page_seo method
Adding corresponding MCP tools
Updating the scoring algorithm
Support
📖 Documentation: Check this README and code comments
🐛 Issues: Report bugs via GitHub Issues
Disclaimer: This tool provides SEO analysis based on current best practices and guidelines. SEO is complex and constantly evolving - always verify recommendations with current SEO guidelines and consider your specific use case.
