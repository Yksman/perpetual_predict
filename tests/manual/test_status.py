"""US-36: Status Message 테스트."""

import asyncio

from perpetual_predict.notifications.alerts import send_status_message
from perpetual_predict.notifications.telegram_bot import TelegramBot
from perpetual_predict.storage.database import Database


async def main():
    bot = TelegramBot()
    db = Database()

    if not bot.is_configured or not bot.enabled:
        print("❌ Telegram 봇이 설정되지 않았거나 비활성화 상태입니다")
        print("   .env 파일의 TELEGRAM_* 설정을 확인하세요")
        return

    await db.initialize()

    print("=== Status Message 테스트 ===")

    result = await send_status_message(bot=bot, database=db, symbol="BTCUSDT")

    print(f"{'✅' if result else '❌'} 상태 메시지 전송")

    await db.close()
    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
