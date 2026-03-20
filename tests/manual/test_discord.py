"""Discord Webhook 테스트."""

import asyncio

from perpetual_predict.notifications.discord_webhook import (
    DiscordEmbed,
    DiscordWebhook,
    EmbedColors,
)


async def main():
    webhook = DiscordWebhook()

    if not webhook.is_configured:
        print("❌ Discord 웹훅이 설정되지 않았습니다")
        print("   DISCORD_WEBHOOK_URL을 .env에 설정하세요")
        print("   DISCORD_ENABLED=true 도 설정해야 합니다")
        return

    if not webhook.enabled:
        print("❌ Discord가 비활성화 상태입니다")
        print("   DISCORD_ENABLED=true를 설정하세요")
        return

    print("=== Discord Webhook 테스트 ===\n")

    # 텍스트 메시지 전송
    print("1. 텍스트 메시지 전송...")
    result = await webhook.send_message(
        "🧪 **테스트 메시지**\n\n이것은 Discord 웹훅 기능 검증 테스트입니다."
    )
    if result:
        print("   ✅ 텍스트 메시지 전송 성공")
    else:
        print("   ❌ 텍스트 메시지 전송 실패")

    # Embed 메시지 전송
    print("\n2. Embed 메시지 전송...")
    embed = (
        DiscordEmbed(
            title="📊 테스트 Embed",
            description="이것은 테스트 Embed 메시지입니다.",
            color=EmbedColors.INFO,
        )
        .add_field(name="Symbol", value="`BTCUSDT`", inline=True)
        .add_field(name="RSI", value="`45.23`", inline=True)
        .add_field(name="Status", value="✅ Normal", inline=True)
        .set_timestamp()
    )
    embed.footer = "Perpetual Predict Test"

    result = await webhook.send_embed(embed)
    if result:
        print("   ✅ Embed 메시지 전송 성공")
    else:
        print("   ❌ Embed 메시지 전송 실패")

    # 다양한 색상 Embed 테스트
    print("\n3. 다양한 색상 Embed 테스트...")

    # Bullish (Green)
    bullish_embed = DiscordEmbed(
        title="🟢 Bullish Signal",
        description="RSI Oversold - Potential bounce incoming",
        color=EmbedColors.BULLISH,
    ).add_field(name="RSI", value="`28.5`", inline=True)

    result = await webhook.send_embed(bullish_embed)
    if result:
        print("   ✅ Bullish embed 전송 성공")
    else:
        print("   ❌ Bullish embed 전송 실패")

    # Bearish (Red)
    bearish_embed = DiscordEmbed(
        title="🔴 Bearish Signal",
        description="RSI Overbought - Potential correction ahead",
        color=EmbedColors.BEARISH,
    ).add_field(name="RSI", value="`78.3`", inline=True)

    result = await webhook.send_embed(bearish_embed)
    if result:
        print("   ✅ Bearish embed 전송 성공")
    else:
        print("   ❌ Bearish embed 전송 실패")

    await webhook.close()
    print("\n=== 테스트 완료 ===")


if __name__ == "__main__":
    asyncio.run(main())
