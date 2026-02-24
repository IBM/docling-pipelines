"""Command-line interface for orchestrating backend services."""
import argparse
import sys
from typing import Optional


def main(args: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="DataSift Orchestrator - Manage backend services"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start a service")
    start_parser.add_argument("service", help="Service name to start")
    start_parser.add_argument("--config", help="Configuration file path")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop a service")
    stop_parser.add_argument("service", help="Service name to stop")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check service status")
    status_parser.add_argument("service", nargs="?", help="Service name (optional)")
    
    # List command
    subparsers.add_parser("list", help="List all available services")
    
    parsed_args = parser.parse_args(args)
    
    if not parsed_args.command:
        parser.print_help()
        return 1
    
    # Handle commands
    if parsed_args.command == "start":
        print(f"Starting service: {parsed_args.service}")
        if parsed_args.config:
            print(f"Using config: {parsed_args.config}")
        return 0
    
    elif parsed_args.command == "stop":
        print(f"Stopping service: {parsed_args.service}")
        return 0
    
    elif parsed_args.command == "status":
        if parsed_args.service:
            print(f"Status of {parsed_args.service}: Running")
        else:
            print("All services status:")
            print("  - service1: Running")
            print("  - service2: Stopped")
        return 0
    
    elif parsed_args.command == "list":
        print("Available services:")
        print("  - service1")
        print("  - service2")
        return 0
    
    return 1


if __name__ == "__main__":
    sys.exit(main())