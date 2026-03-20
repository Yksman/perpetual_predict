"""US-32, US-33: Telegram Bot Client 테스트."""

import asyncio

from perpetual_predict.notifications.telegram_bot import TelegramBot


async def main():
    bot = TelegramBot()

    if not bot.is_configured:
        print("❌ Telegram 봇이 설정되지 않았습니다")
        print("   TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID를 .env에 설정하세요")
        print("   TELEGRAM_ENABLED=true 도 설정해야 합니다")
        return

    if not bot.enabled:
        print("❌ Telegram이 비활성화 상태입니다")
        print("   TELEGRAM_ENABLED=true를 설정하세요")
        return

    print("=== Telegram Bot 테스트 ===")

    # 봇 정보 확인
    bot_info = await bot.get_me()
    if bot_info:
        print(f"✅ 봇 연결 성공: @{bot_info['username']}")
    else:
        print("❌ 봇 연결 실패 - 토큰을 확인하세요")
        await bot.close()
        return

    # 텍스트 메시지 전송
    print("\n메시지 전송 테스트...")
    result = await bot.send_message(
        text="*테스트 메시지*\n\n이것은 Phase 2 기능 검증 테스트입니다.",
        parse_mode="Markdown",
    )

    if result:
        print("✅ 메시지 전송 성공")
    else:
        print("❌ 메시지 전송 실패 - Chat ID를 확인하세요")

    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
