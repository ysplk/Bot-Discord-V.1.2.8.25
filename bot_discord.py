import discord
from discord.ext import commands
import os
import aiohttp
import random
import asyncio
import json
from dotenv import load_dotenv

# --- PERSIAPAN BOT ---
load_dotenv()
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- KONFIGURASI TOKEN & KUNCI API ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- NAMA FILE UNTUK MENYIMPAN SKOR ---
SCORE_FILE = "scores.json"

# --- DATABASE GIF ---
FAIL_GIFS = [
    "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExbW0wcmJkc2JqaHJ2eTRiazVkejRiZXJ3NjlmdmVheW1tanI0dWFlaCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/mEnY8A6zE53pxLRD9a/giphy.gif"
]
WIN_GIFS = [
    "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExYjh3OTE3MWtvd2ZmN2I4a3VhZWF2MXVkaTdoemE0MnVvcDRpc2t0MiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Ju7l5y9osyymQ/giphy.gif"
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

# --- FUNGSI & KELAS UNTUK GAME ---

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
            await channel.send("Jawaban lu bener! �")
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

# --- MENJALANKAN BOT ---
if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("Error: Token Discord tidak ditemukan di file .env. Bot tidak bisa dijalankan.")
