from mail_agent.mcp_server.server import create_server

if __name__ == "__main__":
    create_server().run(transport="stdio")
