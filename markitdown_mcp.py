#!/usr/bin/env python
"""MCP server for MarkItDown - converts documents to Markdown."""
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from markitdown import MarkItDown

server = Server("markitdown")
md = MarkItDown()

TOOLS = [
    Tool(
        name="convert_to_markdown",
        description="Convert a file (PDF, DOCX, XLSX, PPTX, HTML, CSV, JSON, XML, ZIP, images, etc.) to Markdown text.",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to convert"
                }
            },
            "required": ["file_path"]
        }
    ),
    Tool(
        name="convert_from_url",
        description="Download and convert a file from URL to Markdown.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the file to download and convert"
                }
            },
            "required": ["url"]
        }
    )
]

@server.list_tools()
async def list_tools() -> List[Tool]:
    return TOOLS

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    try:
        if name == "convert_to_markdown":
            file_path = arguments["file_path"]
            result = md.convert(file_path)
            return [TextContent(type="text", text=result.text_content)]
        elif name == "convert_from_url":
            url = arguments["url"]
            result = md.convert(url)
            return [TextContent(type="text", text=result.text_content)]
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())