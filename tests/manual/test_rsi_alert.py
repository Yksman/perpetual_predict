"""US-34: RSI Alert 테스트."""

import asyncio

from perpetual_predict.notifications.alerts import send_rsi_alert
from perpetual_predict.notifications.telegram_bot import TelegramBot


async def main():
    bot = TelegramBot()

    if not bot.is_configured or not bot.enabled:
        print("❌ Telegram 봇이 설정되지 않았거나 비활성화 상태입니다")
        print("   .env 파일의 TELEGRAM_* 설정을 확인하세요")
        return

    print("=== RSI Alert 테스트 ===")

    # 과매수 알림 테스트
    print("과매수 알림 전송...")
    result = await send_rsi_alert(
        bot=bot, rsi_value=75.5, signal_type="overbought", symbol="BTCUSDT"
    )
    print(f"{'✅' if result else '❌'} 과매수 알림")

    await asyncio.sleep(1)

    # 과매도 알림 테스트
    print("과매도 알림 전송...")
    result = await send_rsi_alert(
        bot=bot, rsi_value=25.3, signal_type="oversold", symbol="BTCUSDT"
    )
    print(f"{'✅' if result else '❌'} 과매도 알림")

    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
