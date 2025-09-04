import discord
from discord.ext import commands
import os
import aiohttp
import random
import asyncio
import json
from dotenv import load_dotenv

# --- Tambahan buat Musik & Spotify ---
import yt_dlp
import functools
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# --- PERSIAPAN BOT ---
load_dotenv()
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.voice_states = True # <-- PENTING: Izin buat liat status voice
bot = commands.Bot(command_prefix="!", intents=intents)

# --- KONFIGURASI TOKEN & KUNCI API ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

# --- Inisialisasi Klien Spotify ---
if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET:
    try:
        auth_manager = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
        sp = spotipy.Spotify(auth_manager=auth_manager)
        print("Klien Spotify berhasil diinisialisasi.")
    except Exception as e:
        sp = None
        print(f"Gagal inisialisasi klien Spotify: {e}")
else:
    sp = None
    print("Peringatan: Kredensial Spotify tidak ditemukan di .env. Fitur Spotify tidak akan aktif.")

# --- JURUS PAMUNGKAS BUAT COOKIES YOUTUBE ---
YT_COOKIES_CONTENT = os.getenv("YT_COOKIES")
COOKIE_FILENAME = "youtube.com_cookies.txt"

if YT_COOKIES_CONTENT:
    try:
        # Tulis isi dari environment variable ke dalem file
        with open(COOKIE_FILENAME, 'w') as f:
            f.write(YT_COOKIES_CONTENT)
        print("File cookies YouTube berhasil dibuat dari environment variable.")
    except Exception as e:
        print(f"Gagal nulis file cookies dari env var: {e}")
# --- AKHIR JURUS PAMUNGKAS ---


# --- NAMA FILE UNTUK MENYIMPAN SKOR ---
SCORE_FILE = "scores.json"

# --- DATABASE GIF ---
FAIL_GIFS = [
    "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExbW0wcmJkc2JqaHJ2eTRiazVkejRiZXJ3NjlmdmVheW1tanI0dWFlaCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/mEnY8A6zE53pxLRD9a/giphy.gif"
]
WIN_GIFS = [
    "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExYjh3OTE3MWtvd2ZmN2I4a3VhZWF2MXVkaTdoemE0MnVvcDRpc2t0MiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Ju7l5y99osyymQ/giphy.gif"
]
FIGHT_GIFS = [
    "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExb2szYnRrdXZ4ZHFoaG03YnJjeXZoa3M2cTFhc3pmMW5lNXN4ODJsMCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/NBAOL4ZPU4Pks/giphy.gif"
]
RUN_GIFS = [
    "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExb2szYnRrdXZ4ZHFoaG03YnJjeXZoa3M2cTFhc3pmMW5lNXN4ODJsMCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/NBAOL4ZPU4Pks/giphy.gif"
]

game_states = {}

# --- FUNGSI UNTUK MENGELOLA SKOR ---

def load_scores():
    """Memuat skor dari file scores.json."""
    if not os.path.exists(SCORE_FILE):
        return {}
    try:
        with open(SCORE_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_scores(scores):
    """Menyimpan skor ke file scores.json."""
    with open(SCORE_FILE, 'w') as f:
        json.dump(scores, f, indent=4)

# --- EVENT & COMMANDS ---

@bot.event
async def on_ready():
    print(f"Bot telah masuk sebagai {bot.user}")
    print("Bot siap menerima perintah!")

# --- FUNGSI & KELAS UNTUK GAME (KODE LAMA LU, AMAN) ---

async def generate_and_start_quiz(interaction: discord.Interaction, language: str):
    author_id = interaction.user.id
    await interaction.response.edit_message(content=f"Oke, si kakek lagi mikirin pertanyaan dalam {language}... Bentar ya...", embed=None, view=None)

    if not GEMINI_API_KEY:
        await interaction.channel.send("Waduh, API Key buat bikin pertanyaan belom diatur nih. Kuis gagal dimulai.")
        return

    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}"
    prompt = (
        f"Buatkan 5 pertanyaan pengetahuan umum dari kategori (Geografi, Sejarah, Sains, Teknologi, dan Sastra) dalam {language} yang singkat dan padat. "
        "Berikan jawaban yang singkat juga (satu atau dua kata). "
        "Format output harus berupa JSON array dari objek, di mana setiap objek punya key 'q' untuk pertanyaan dan 'a' untuk jawaban. "
        "Jawaban harus dalam huruf kecil semua. Contoh: [{'q': 'Ibu kota Perancis?', 'a': 'paris'}]"
    )
    payload = {"contents": [{"parts":[{"text": prompt}]}]}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    json_text = data['candidates'][0]['content']['parts'][0]['text'].strip().replace("```json", "").replace("```", "")
                    questions = json.loads(json_text)

                    game_states[author_id] = {"game_type": "quiz", "score": 0, "questions": questions, "current_q": 0}
                    embed = discord.Embed(title="Kuis dari Kakek Dimulai!", description="Jawab 5 pertanyaan di bawah ini secepatnya!", color=discord.Color.gold())
                    await interaction.channel.send(embed=embed)
                    await ask_quiz_question(interaction.channel, interaction.user)
                else:
                    error_text = await response.text()
                    await interaction.channel.send(f"Waduh, si kakek lagi pusing, gagal bikin pertanyaan. Coba lagi nanti. Error: {response.status}\n`{error_text}`")
    except Exception as e:
        await interaction.channel.send(f"Anjir, error bray! Gagal nyambung ke otak si kakek. Coba lagi ntar.\nDetail: `{e}`")

class LanguageSelectionView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=60)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Ini bukan pilihan lu, bray!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Bahasa Indonesia", style=discord.ButtonStyle.primary, emoji="🇮🇩")
    async def select_indonesian(self, interaction: discord.Interaction, button: discord.ui.Button):
        await generate_and_start_quiz(interaction, "Bahasa Indonesia")

    @discord.ui.button(label="English", style=discord.ButtonStyle.secondary, emoji="🇬🇧")
    async def select_english(self, interaction: discord.Interaction, button: discord.ui.Button):
        await generate_and_start_quiz(interaction, "English")

class AdventureStartView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=60)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Ini bukan petualangan lu, bray!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Masuk Hutan", style=discord.ButtonStyle.danger, emoji="🌳")
    async def go_to_forest(self, interaction: discord.Interaction, button: discord.ui.Button):
        game_states[self.author_id] = {"game_type": "adventure"}
        embed = discord.Embed(title="Masuk ke Hutan Gelap", description="Lu milih masuk ke hutan. Suasananya serem, banyak suara aneh. Tiba-tiba dari balik semak muncul seekor beruang gede lagi marah!", color=discord.Color.dark_green())
        await interaction.response.edit_message(content=None, embed=embed, view=BearEncounterView(self.author_id))

    @discord.ui.button(label="Pergi ke Desa", style=discord.ButtonStyle.success, emoji="🏘️")
    async def go_to_village(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Menuju Desa...", description="Lu milih jalan ke desa dan ketemu seorang kakek. Sebelum ngasih pertanyaan, dia nanya lu mau kuisnya pake bahasa apa?", color=discord.Color.gold())
        await interaction.response.edit_message(content=None, embed=embed, view=LanguageSelectionView(self.author_id))

class BearEncounterView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=60)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Ini bukan beruang lu, bray!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Lawan Beruang", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def fight_bear(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="KALAH TELAK!", description="Lu nekat ngelawan beruang pake tangan kosong. Ya jelas aja lu dicabik-cabik. Petualangan lu berakhir tragis.", color=discord.Color.red())
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        await interaction.followup.send(random.choice(FIGHT_GIFS))
        if self.author_id in game_states:
            del game_states[self.author_id]

    @discord.ui.button(label="Kabur!", style=discord.ButtonStyle.secondary, emoji="🏃")
    async def run_from_bear(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="SELAMAT!", description="Lu lari sekenceng-kencengnya dan berhasil lolos dari beruang. Lu aman, tapi sekarang lu nyasar di dalem hutan. Petualangan lu berakhir di sini.", color=discord.Color.light_grey())
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        await interaction.followup.send(random.choice(RUN_GIFS))
        if self.author_id in game_states:
            del game_states[self.author_id]

async def ask_quiz_question(channel, user):
    state = game_states.get(user.id)
    if not state:
        return

    if state["current_q"] >= len(state["questions"]):
        score = state['score']
        passing_score = 3

        if score >= passing_score:
            scores = load_scores()
            user_id_str = str(user.id)
            scores[user_id_str] = scores.get(user_id_str, 0) + 1
            save_scores(scores)
            
            embed = discord.Embed(title="Kuis Selesai! Lu Menang!", description=f"Mantep! Lu berhasil jawab {score} dari 5 pertanyaan dengan bener.\n**Skor lu nambah 1!**", color=discord.Color.green())
            await channel.send(embed=embed)
            await channel.send(random.choice(WIN_GIFS))
        else:
            embed = discord.Embed(title="Kuis Selesai! Lu Kalah!", description=f"Yah, lu cuma bener {score} dari 5. Coba lagi lain kali!", color=discord.Color.dark_red())
            await channel.send(embed=embed)
            await channel.send(random.choice(FAIL_GIFS))
            
        if user.id in game_states:
            del game_states[user.id]
        return

    question_data = state["questions"][state["current_q"]]
    q_embed = discord.Embed(title=f"Pertanyaan #{state['current_q'] + 1}", description=question_data["q"], color=discord.Color.orange())
    await channel.send(embed=q_embed)

    def check(m):
        return m.author.id == user.id and m.channel.id == channel.id

    try:
        msg = await bot.wait_for('message', timeout=30.0, check=check)
        if msg.content.lower().strip() == question_data["a"].lower().strip():
            await channel.send("Jawaban lu bener! 👍")
            state["score"] += 1
        else:
            await channel.send(f"Salah, bray! Jawaban yang bener itu: **{question_data['a']}**")
        
        state["current_q"] += 1
        await ask_quiz_question(channel, user)

    except asyncio.TimeoutError:
        await channel.send("Waktu abis, bray! Kuis dibatalin.")
        if user.id in game_states:
            del game_states[user.id]

@bot.command(name="quiz")
async def adventure_start(ctx):
    """Memulai game petualangan berbasis pilihan."""
    if ctx.author.id in game_states:
        await ctx.send("Lu lagi di tengah game, selesain dulu yang itu!")
        return
    
    embed = discord.Embed(title="Petualangan Dimulai!", description=f"Halo {ctx.author.mention}, lu tersesat dan sekarang ada di depan sebuah persimpangan. Lu mau milih jalan yang mana?", color=discord.Color.purple())
    view = AdventureStartView(ctx.author.id)
    await ctx.send(embed=embed, view=view)

@bot.command(name="skor")
async def leaderboard(ctx):
    """Menampilkan papan skor 10 pemain teratas."""
    scores = load_scores()
    if not scores:
        await ctx.send("Belom ada yang punya skor, bray. Main gih sana!")
        return

    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    embed = discord.Embed(title="🏆 Papan Skor Kuis Teratas 🏆", description="Ini dia para jagoan kuis di server!", color=discord.Color.gold())

    for i, (user_id, score) in enumerate(sorted_scores[:10]):
        try:
            user = await bot.fetch_user(int(user_id))
            user_name = user.display_name
        except discord.NotFound:
            user_name = f"Pengguna Misterius (ID: {user_id})"
        
        embed.add_field(name=f"#{i+1} - {user_name}", value=f"**{score}** kemenangan", inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"Informasi Server: {guild.name}", description="Berikut adalah detail dari server ini.", color=discord.Color.blue())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Nama Server", value=guild.name, inline=True)
    embed.add_field(name="ID Server", value=guild.id, inline=True)
    embed.add_field(name="Pemilik Server", value=guild.owner.mention, inline=False)
    embed.add_field(name="Jumlah Anggota", value=guild.member_count, inline=True)
    embed.add_field(name="Jumlah Channel", value=len(guild.text_channels) + len(guild.voice_channels), inline=True)
    embed.add_field(name="Dibuat pada", value=guild.created_at.strftime("%d %B %Y, %H:%M"), inline=False)
    embed.set_footer(text=f"Diminta oleh: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else "")
    await ctx.send(embed=embed)

@bot.command(name="tanya")
async def ask_gemini(ctx, *, question: str):
    if not GEMINI_API_KEY:
        await ctx.send("Waduh, API Key buat ngobrol sama AI belom diatur nih sama yang punya bot.")
        return
    thinking_message = await ctx.send("Bentar ya, gue lagi mikir...")
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts":[{"text": question}]}]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    answer = data['candidates'][0]['content']['parts'][0]['text']
                    await thinking_message.delete()
                    header = f"**Pertanyaan lu:**\n> {question}\n\n**Jawaban dari gue:**\n"
                    if len(header) + len(answer) <= 2000:
                        await ctx.send(header + answer)
                    else:
                        await ctx.send(header)
                        chunk_size = 1990
                        for i in range(0, len(answer), chunk_size):
                            await ctx.send(answer[i:i+chunk_size])
                else:
                    error_text = await response.text()
                    await thinking_message.edit(content=f"Waduh, ada masalah pas nanya ke AI nih. Error: {response.status}\n`{error_text}`")
    except Exception as e:
        await thinking_message.edit(content=f"Anjir, error bray! Gagal nyambung ke otaknya AI. Coba lagi ntar.\nDetail: `{e}`")

# --- MODUL MUSIK ---

# --- OPSI YTDL DI-UPDATE BUAT PAKE COOKIES ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'auto',
    'quiet': True,
    'no_warnings': True,
    'cookiefile': COOKIE_FILENAME # Pake nama file dari variabel di atas
}

# Opsi buat FFmpeg biar koneksi stabil
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

# Tempat nyimpen antrian lagu buat tiap server
music_queues = {}

# Fungsi buat ngambil info lagu pake yt-dlp (dijalanin di thread terpisah biar bot gak nge-freeze)
async def get_song_info(query):
    loop = asyncio.get_event_loop()
    partial_func = functools.partial(yt_dlp.YoutubeDL(YTDL_OPTIONS).extract_info, query, download=False)
    data = await loop.run_in_executor(None, partial_func)
    
    if 'entries' in data:
        # Kalo hasil search, ambil yang pertama
        data = data['entries'][0]
        
    return {'url': data['url'], 'title': data['title']}

# --- FUNGSI PLAY_NEXT YANG SUDAH DI-UPGRADE ---
async def play_next(ctx):
    guild_id = ctx.guild.id
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        if guild_id in music_queues:
            del music_queues[guild_id] 
        return

    if ctx.voice_client.is_playing():
        return

    if guild_id in music_queues and not music_queues[guild_id].empty():
        song = await music_queues[guild_id].get()
        
        def after_playing(error):
            if error:
                print(f"Anjir, error pas muter lagu: {error}")
                coro = ctx.send(f"Waduh, ada error pas muter lagu, bray. Mungkin lagunya gak bisa diakses.\n`{error}`")
            else:
                print("Lagu selesai diputer.")
            
            fut = asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
            try:
                fut.result(timeout=5)
            except Exception as e:
                print(f"Error pas ngejalanin play_next dari after_playing: {e}")

        try:
            source = discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS)
            ctx.voice_client.play(source, after=after_playing)
            
            embed = discord.Embed(title="🎶 Lagi Muterin", description=f"**{song['title']}**", color=discord.Color.purple())
            await ctx.send(embed=embed)
        except Exception as e:
            # --- BAGIAN INI DI-UPDATE BIAR LEBIH JELAS ---
            error_message = f"Gila, error pas mau mulai muter lagu: `{e}`"
            print(error_message) # Cetak error ke konsol Railway biar bisa diliat
            await ctx.send(error_message) # Kirim errornya ke chat juga
            await play_next(ctx)
    else:
        print("Antrian kosong, bot diem di channel.")

# --- KUMPULAN PERINTAH MUSIK (COG) ---
class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="join", help="Nongol di voice channel lu")
    async def join(self, ctx):
        if not ctx.author.voice:
            await ctx.send("Lu aja belom masuk voice channel, bray!")
            return
        
        channel = ctx.author.voice.channel
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(f"Udah join ke **{channel.name}**!")

    @commands.command(name="play", help="Muterin lagu dari YouTube atau Spotify (link atau judul)")
    async def play(self, ctx, *, query: str):
        if not ctx.author.voice:
            await ctx.send("Masuk voice channel dulu, baru nyetel lagu!")
            return

        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)

        if ctx.guild.id not in music_queues:
            music_queues[ctx.guild.id] = asyncio.Queue()

        # --- LOGIKA BARU BUAT SPOTIFY ---
        search_query = query
        spotify_track_regex = r"(https?://)?(www\.)?open\.spotify\.com/track/([a-zA-Z0-9]+)"
        match = re.match(spotify_track_regex, query)

        if match and sp:
            try:
                track_id = match.group(3)
                track = sp.track(track_id)
                track_name = track['name']
                artist_name = track['artists'][0]['name']
                search_query = f"{track_name} {artist_name}"
                await ctx.send(f"🔍 Nemu lagu Spotify: **{track_name} - {artist_name}**. Nyari di YouTube...")
            except Exception as e:
                await ctx.send(f"Waduh, gagal ngambil info dari link Spotify itu. Error: `{e}`")
                return
        elif match and not sp:
            await ctx.send("Fitur Spotify belom aktif, bray. Cek lagi `SPOTIPY_CLIENT_ID` dan `SPOTIPY_CLIENT_SECRET` di file .env lu.")
            return
        # --- AKHIR LOGIKA SPOTIFY ---

        try:
            song = await get_song_info(search_query)
            await music_queues[ctx.guild.id].put(song)
            await ctx.send(f"✅ **{song['title']}** udah masuk antrian!")

            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await play_next(ctx)

        except Exception as e:
            await ctx.send(f"Waduh, error pas nyari lagu: `{str(e)}`")


    @commands.command(name="skip", help="Ngelewatin lagu yang lagi diputer")
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Lagu di-skip!")
        else:
            await ctx.send("Lagi gak ada lagu yang diputer, bray.")
            
    @commands.command(name="pause", help="Jeda lagu yang lagi diputer")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Lagu di-pause. Pake `!resume` buat lanjutin.")
        else:
            await ctx.send("Gak ada lagu yang lagi muter buat di-pause.")

    @commands.command(name="resume", help="Lanjutin lagi lagu yang di-pause")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Lagu dilanjutin!")
        else:
            await ctx.send("Gak ada lagu yang lagi di-pause.")

    @commands.command(name="stop", help="Berhentiin musik dan keluar dari voice channel")
    async def stop(self, ctx):
        if ctx.voice_client:
            if ctx.guild.id in music_queues:
                while not music_queues[ctx.guild.id].empty():
                    await music_queues[ctx.guild.id].get()
            
            await ctx.voice_client.disconnect()
            await ctx.send("Oke, gua cabut. Makasih udah dengerin!")
        else:
            await ctx.send("Gua aja kaga di voice channel.")

    @commands.command(name="queue", help="Nampilin daftar antrian lagu")
    async def queue(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in music_queues or music_queues[guild_id].empty():
            await ctx.send("Antrian lagu kosong, bray!")
            return

        embed = discord.Embed(title="📜 Antrian Lagu", color=discord.Color.blue())
        queue_list = list(music_queues[guild_id]._queue)

        for i, song in enumerate(queue_list):
            embed.add_field(name=f"#{i+1}. {song['title']}", value=" ", inline=False)
        
        await ctx.send(embed=embed)

# --- MODUL MODERASI (BARU!) ---
class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="kick", help="Nendang anggota dari server.")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Gak ada alesan, iseng aja."):
        if member == ctx.author:
            await ctx.send("Lu gabisa nendang diri sendiri, bray.")
            return
        if member == self.bot.user:
            await ctx.send("Gak bisa nendang gua dong!")
            return
            
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Anggota Ditendang", color=discord.Color.orange())
        embed.add_field(name="Anggota", value=member.mention, inline=False)
        embed.add_field(name="Alesan", value=reason, inline=False)
        embed.set_footer(text=f"Ditendang oleh: {ctx.author.name}")
        await ctx.send(embed=embed)

    @commands.command(name="ban", help="Nge-ban anggota dari server.")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "Gak ada alesan spesifik."):
        if member == ctx.author:
            await ctx.send("Lu gabisa nge-ban diri sendiri, bray.")
            return
        if member == self.bot.user:
            await ctx.send("Gak bisa nge-ban gua dong!")
            return

        await member.ban(reason=reason)
        embed = discord.Embed(title="🚫 Anggota Di-Ban", color=discord.Color.red())
        embed.add_field(name="Anggota", value=member.mention, inline=False)
        embed.add_field(name="Alesan", value=reason, inline=False)
        embed.set_footer(text=f"Di-ban oleh: {ctx.author.name}")
        await ctx.send(embed=embed)

    @commands.command(name="move", help="Mindahin anggota ke voice channel lain.")
    @commands.has_permissions(move_members=True)
    async def move(self, ctx, member: discord.Member, channel: discord.VoiceChannel):
        if not member.voice:
            await ctx.send(f"{member.mention} lagi gak ada di voice channel.")
            return
        
        await member.move_to(channel)
        await ctx.send(f"Berhasil mindahin {member.mention} ke **{channel.name}**!")

    # Error handling buat yang gak punya izin
    @kick.error
    @ban.error
    @move.error
    async def moderation_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Lu kaga punya izin buat pake perintah ini, bray!")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("Gak nemu anggota itu di server ini.")
        elif isinstance(error, commands.ChannelNotFound):
             await ctx.send("Gak nemu voice channel itu.")
        else:
            await ctx.send(f"Anjir, ada error: `{error}`")


# --- MENJALANKAN BOT DENGAN CARA MODERN ---
async def main():
    if not DISCORD_TOKEN:
        print("Error: Token Discord tidak ditemukan di file .env. Bot tidak bisa dijalankan.")
        return
        
    async with bot:
        await bot.add_cog(MusicCog(bot))      # 'Nempel'in modul musik ke bot
        await bot.add_cog(ModerationCog(bot)) # 'Nempel'in modul hansip ke bot
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot dimatiin.")

