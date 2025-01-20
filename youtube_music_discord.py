import asyncio

import discord
import yt_dlp
from discord.ext import commands

# ボットの設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(
    command_prefix="y!", intents=intents, help_command=None
)  # help_command=Noneでデフォルトのhelpコマンドを無効化

# FFMPEGの設定
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

# キュー（再生待ちリスト）
song_queue = asyncio.Queue()
queue_list = []  # 表示用のリスト


async def play_next(ctx):
    """キューに曲があれば次の曲を再生する"""
    if not song_queue.empty():
        url, title = await song_queue.get()
        queue_list.pop(0)  # 先頭を削除
        await play_audio(ctx, url, title)


async def play_audio(ctx, url, title):
    """YouTubeから音声を取得し、ボイスチャンネルで再生"""
    if ctx.author.voice is None:
        await ctx.send("ボイスチャンネルに参加してください。")
        return

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None or not ctx.voice_client.is_connected():
        voice_client = await voice_channel.connect()
    else:
        voice_client = ctx.voice_client

    # YouTubeの音声URLを取得
    ydl_opts = {"format": "bestaudio/best", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        url2 = info["url"]

    # 音声を再生
    def after_playing(error):
        if error:
            print(f"Error: {error}")
        asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)

    voice_client.play(
        discord.FFmpegPCMAudio(url2, **FFMPEG_OPTIONS), after=after_playing
    )
    await ctx.send(f"🎵 再生中: {title}")


async def add_playlist(ctx, playlist_url):
    """YouTubeプレイリストの全動画をキューに追加"""
    ydl_opts = {"extract_flat": True, "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

        if "entries" not in info:
            await ctx.send("❌ プレイリストが見つかりませんでした。")
            return

        for entry in info["entries"]:
            if "url" in entry:
                await song_queue.put((entry["url"], entry["title"]))
                queue_list.append(entry["title"])

        await ctx.send(
            f"✅ プレイリストから {len(info['entries'])} 曲をキューに追加しました。"
        )


@bot.command()
async def play(ctx, url: str):
    """URLがプレイリストなら全曲追加、動画なら1曲追加"""
    if "playlist" in url:
        await add_playlist(ctx, url)
    else:
        ydl_opts = {"format": "bestaudio/best", "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        await song_queue.put((url, info["title"]))
        queue_list.append(info["title"])
        await ctx.send(f"✅ キューに追加: {info['title']}")

    # 再生中でなければ開始
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await play_next(ctx)


@bot.command()
async def skip(ctx):
    """現在の曲をスキップして次の曲を再生"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()  # 再生を停止し、after_playing() をトリガー
        await ctx.send("⏭️ 曲をスキップしました。")
    else:
        await ctx.send("🎵 再生中の曲がありません。")


@bot.command()
async def stop(ctx):
    """キューをリセットし、ボイスチャンネルから退出"""
    global song_queue, queue_list
    song_queue = asyncio.Queue()  # キューをリセット
    queue_list = []  # 表示用リストもクリア
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ すべての曲を停止し、ボイスチャンネルから退出しました。")
    else:
        await ctx.send("ボットはボイスチャンネルに接続していません。")


@bot.command()
async def queue(ctx):
    """現在のキューを表示"""
    if not queue_list:
        await ctx.send("🎵 キューは空です。")
    else:
        queue_msg = "\n".join(
            [f"{i + 1}. {title}" for i, title in enumerate(queue_list[:10])]
        )
        if len(queue_list) > 10:
            queue_msg += f"\n... 他 {len(queue_list) - 10} 曲"
        await ctx.send(f"📜 **再生キュー:**\n{queue_msg}")


@bot.command()
async def help(ctx):
    """カスタム help コマンド"""
    help_msg = """
**使用方法**

`y!play <URL>` : YouTube の動画またはプレイリストを再生します。
   - プレイリストの場合、全ての曲が順番に再生されます。

`y!skip` : 現在の曲をスキップして、次の曲を再生します。

`y!stop` : 再生を停止し、ボイスチャンネルから退出します。キューもリセットされます。

`y!queue` : 現在の再生キューを表示します。（最大10曲）

`y!help` : このヘルプメッセージを表示します。

**注意:**
- プレイリストを再生する場合、`y!play <プレイリストURL>` と入力。公開されていない場合は参照できないため追加できない。

    """
    await ctx.send(help_msg)


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")


# ボットの実行
bot.run("YOUR BOT TOKEN")
