"""
Script auxiliar para configurar o bot do Telegram.

Instruções:
1. Abra o Telegram e procure @BotFather
2. Envie /newbot e siga as instruções
3. Copie o token do bot
4. Adicione o bot ao seu grupo
5. Execute este script: python setup_telegram.py
"""

import asyncio
import sys

from telegram import Bot


async def main():
    print("=" * 50)
    print("CONFIGURAÇÃO DO BOT TELEGRAM — ROP Odds System")
    print("=" * 50)
    print()
    print("Passo 1: Crie um bot no Telegram")
    print("  1. Abra o Telegram e procure @BotFather")
    print("  2. Envie /newbot")
    print("  3. Escolha um nome (ex: ROP Odds Alert)")
    print("  4. Escolha um username (ex: rop_odds_bot)")
    print("  5. Copie o token que o BotFather enviar")
    print()

    token = input("Cole o token do bot aqui: ").strip()
    if not token:
        print("Token vazio. Saindo.")
        return

    print()
    print("Conectando ao bot...")

    try:
        bot = Bot(token=token)
        me = await bot.get_me()
        print(f"✅ Bot conectado: @{me.username} ({me.first_name})")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return

    print()
    print("Passo 2: Obter o Chat ID do grupo")
    print("  1. Adicione o bot (@{}) ao seu grupo do Telegram".format(me.username))
    print("  2. Envie uma mensagem qualquer no grupo")
    print("  3. Pressione Enter aqui para buscar o Chat ID")
    print()

    input("Pressione Enter após enviar uma mensagem no grupo...")

    try:
        updates = await bot.get_updates()
        chat_ids = set()
        for update in updates:
            if update.message and update.message.chat:
                chat = update.message.chat
                chat_ids.add((chat.id, chat.title or chat.first_name or "DM"))

        if not chat_ids:
            print("❌ Nenhuma mensagem encontrada. Envie uma mensagem no grupo e tente novamente.")
            return

        print("\nChats encontrados:")
        for cid, title in chat_ids:
            print(f"  • {title}: {cid}")

        chat_id = input("\nCole o Chat ID do grupo desejado: ").strip()
    except Exception as e:
        print(f"❌ Erro: {e}")
        return

    # Test sending
    print("\nEnviando mensagem de teste...")
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="✅ *ROP Odds System* configurado com sucesso!\n\nOs relatórios de odds serão enviados aqui.",
            parse_mode="Markdown",
        )
        print("✅ Mensagem enviada com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")
        return

    # Save to .env
    print()
    print("=" * 50)
    print("CONFIGURAÇÃO CONCLUÍDA!")
    print("=" * 50)
    print()
    print("Adicione estas linhas ao seu arquivo .env:")
    print()
    print(f"TELEGRAM_BOT_TOKEN={token}")
    print(f"TELEGRAM_CHAT_ID={chat_id}")
    print()

    save = input("Deseja salvar automaticamente no .env? (s/n): ").strip().lower()
    if save == "s":
        with open(".env", "a") as f:
            f.write(f"\nTELEGRAM_BOT_TOKEN={token}\n")
            f.write(f"TELEGRAM_CHAT_ID={chat_id}\n")
        print("✅ Salvo no .env!")


if __name__ == "__main__":
    asyncio.run(main())
