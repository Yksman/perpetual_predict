"""US-35: Support/Resistance Alert 테스트."""

import asyncio

from perpetual_predict.notifications.alerts import send_sr_alert
from perpetual_predict.notifications.telegram_bot import TelegramBot


async def main():
    bot = TelegramBot()

    if not bot.is_configured or not bot.enabled:
        print("❌ Telegram 봇이 설정되지 않았거나 비활성화 상태입니다")
        print("   .env 파일의 TELEGRAM_* 설정을 확인하세요")
        return

    print("=== Support/Resistance Alert 테스트 ===")

    # 지지선 알림 테스트
    print("지지선 알림 전송...")
    result = await send_sr_alert(
        bot=bot,
        price=67150.00,
        level=67000.00,
        level_type="support",
        symbol="BTCUSDT",
    )
    print(f"{'✅' if result else '❌'} 지지선 알림")

    await asyncio.sleep(1)

    # 저항선 알림 테스트
    print("저항선 알림 전송...")
    result = await send_sr_alert(
        bot=bot,
        price=69850.00,
        level=70000.00,
        level_type="resistance",
        symbol="BTCUSDT",
    )
    print(f"{'✅' if result else '❌'} 저항선 알림")

    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
