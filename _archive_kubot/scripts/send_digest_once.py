#!/usr/bin/env python3
"""Manual trigger script for sending daily digest once."""

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

from bot.tasks.digest import send_daily_digest, cleanup


async def main():
    """Run daily digest send and display results."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    logger = logging.getLogger(__name__)
    
    print("🚀 Starting manual digest send...")
    print(f"📅 Time: {datetime.now().isoformat()}")
    print("=" * 50)
    
    try:
        # Send digest
        stats = await send_daily_digest()
        
        # Display results
        print("\n📊 DIGEST SEND RESULTS")
        print("=" * 50)
        print(f"🕐 Started: {stats.get('started_at', 'N/A')}")
        print(f"🕐 Completed: {stats.get('completed_at', 'N/A')}")
        print(f"⏱️  Duration: {stats.get('duration_seconds', 0):.1f}s")
        print()
        print(f"👥 Total Users: {stats.get('total_users', 0)}")
        print(f"✅ Successful: {stats.get('successful_sends', 0)}")
        print(f"❌ Failed: {stats.get('failed_sends', 0)}")
        print(f"🚫 Blocked: {stats.get('blocked_users', 0)}")
        print(f"📦 Batches: {stats.get('batches_processed', 0)}")
        
        # Language breakdown
        languages = stats.get('languages', {})
        if languages:
            print("\n🌐 LANGUAGE BREAKDOWN")
            print("-" * 30)
            for lang, lang_stats in languages.items():
                print(f"{lang.upper()}:")
                print(f"  📊 Total: {lang_stats.get('total', 0)}")
                print(f"  ✅ Success: {lang_stats.get('successful', 0)}")
                print(f"  ❌ Failed: {lang_stats.get('failed', 0)}")
                print(f"  🚫 Blocked: {lang_stats.get('blocked', 0)}")
        
        # Check for errors
        if 'error' in stats:
            print(f"\n❌ ERROR: {stats['error']}")
            return 1
        
        print(f"\n🎉 Digest send completed successfully!")
        
        if stats.get('successful_sends', 0) == 0:
            print("⚠️  No messages were sent successfully.")
            return 1
            
        return 0
        
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        print(f"\n💥 FATAL ERROR: {e}")
        return 1
        
    finally:
        # Cleanup
        await cleanup()


if __name__ == "__main__":
    # Check environment
    if not os.getenv("BOT_TOKEN"):
        print("❌ BOT_TOKEN environment variable is required")
        sys.exit(1)
    
    # Run the script
    exit_code = asyncio.run(main())
    sys.exit(exit_code)