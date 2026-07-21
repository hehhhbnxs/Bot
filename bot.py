import discord
from discord.ext import commands, tasks
from discord.app_commands import default_permissions
import json
import random
import os
import aiohttp
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

# ====================================================================
# --- PHẦN 1: WEB SERVER CHO RENDER & CẤU HÌNH ---
# ====================================================================
app = Flask('')
@app.route('/')
def home(): 
    return "✅ Bot đang chạy trên Render!"

def run_web():
    try: app.run(host='0.0.0.0', port=8080)
    except: pass

def keep_alive():
    t = Thread(target=run_web)
    t.start()

TOKEN = os.environ.get('DISCORD_TOKEN')
SERVER_IP = os.environ.get('SERVER_IP', '') 

try:
    CONSOLE_CHANNEL_ID = int(os.environ.get('CONSOLE_CHANNEL_ID', 0)) 
    BACKUP_CHANNEL_ID = int(os.environ.get('BACKUP_CHANNEL_ID', 0))   
    NOITU_CHANNEL_ID = int(os.environ.get('NOITU_CHANNEL_ID', 0))     
except ValueError:
    CONSOLE_CHANNEL_ID = 0
    BACKUP_CHANNEL_ID = 0
    NOITU_CHANNEL_ID = 0

DB_FILE = 'users.json'
data_changed = False

# --- QUẢN LÝ DATABASE ---
def load_db():
    if not os.path.exists(DB_FILE): 
        return {"users": {}}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "users" not in data: data = {"users": data}
            return data
    except: 
        return {"users": {}}

def save_db(data):
    global data_changed
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f: 
            json.dump(data, f, indent=4, ensure_ascii=False)
        data_changed = True
    except Exception as e: 
        print(f"Lỗi lưu file: {e}")

# ====================================================================
# --- PHẦN 2: HỆ THỐNG NỐI TỪ (BẢN NÂNG CẤP) ---
# ====================================================================
STARTING_WORDS = ["thời tiết", "gia đình", "máy tính", "bầu trời", "con mèo", "xe đạp", "hoa hồng", "âm nhạc", "hạnh phúc", "công việc", "bóng đá", "học tập", "tình yêu", "kết quả", "thành công"]

class NoiTuGame:
    def __init__(self):
        self.current_word = random.choice(STARTING_WORDS)
        self.last_player_id = None
        self.used_words = {self.current_word}
        self.streak = 0

    def reset(self):
        self.current_word = random.choice(STARTING_WORDS)
        self.last_player_id = None
        self.used_words = {self.current_word}
        self.streak = 0

game_noitu = NoiTuGame()

# ====================================================================
# --- PHẦN 3: GIAO DIỆN BẦU CUA ---
# ====================================================================
class BauCuaView(discord.ui.View):
    def __init__(self, host_id):
        super().__init__(timeout=120)
        self.host_id = host_id
        self.bets = {} 

    async def prompt_bet(self, i, choice, emoji): 
        await i.response.send_modal(BetModal(choice, emoji, self))
        
    @discord.ui.button(label="Bầu", emoji="🥒")
    async def btn_b(self, i, b): await self.prompt_bet(i, "bầu", "🥒")
    @discord.ui.button(label="Cua", emoji="🦀")
    async def btn_c(self, i, b): await self.prompt_bet(i, "cua", "🦀")
    @discord.ui.button(label="Tôm", emoji="🦐")
    async def btn_t(self, i, b): await self.prompt_bet(i, "tôm", "🦐")
    @discord.ui.button(label="Cá", emoji="🐟", row=1)
    async def btn_ca(self, i, b): await self.prompt_bet(i, "cá", "🐟")
    @discord.ui.button(label="Gà", emoji="🐔", row=1)
    async def btn_g(self, i, b): await self.prompt_bet(i, "gà", "🐔")
    @discord.ui.button(label="Nai", emoji="🦌", row=1)
    async def btn_n(self, i, b): await self.prompt_bet(i, "nai", "🦌")

    @discord.ui.button(label="🎲 CHỐT SỔ & LẮC", style=discord.ButtonStyle.danger, row=2)
    async def btn_roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id: 
            return await interaction.response.send_message("❌ Chỉ chủ bàn mới được lắc!", ephemeral=True)
        self.stop()
        await interaction.response.defer()
        
        ket_qua = [random.choice(['bầu', 'cua', 'tôm', 'cá', 'gà', 'nai']) for _ in range(3)]
        db = load_db()
        msg = f"🎲 **KẾT QUẢ:** [ **{' - '.join([x.capitalize() for x in ket_qua])}** ]\n\n**BẢNG TRẢ THƯỞNG:**\n"
        
        if not self.bets: 
            msg += "Không có ai tham gia cược!"
        else:
            for uid, bets in self.bets.items():
                tong_nhan, tong_cuoc = 0, sum(b['amount'] for b in bets)
                for b in bets:
                    so_lan = ket_qua.count(b['animal'])
                    if so_lan > 0: 
                        tong_nhan += b['amount'] + (b['amount'] * so_lan)
                        
                if tong_nhan > 0: 
                    db["users"][uid]["balance"] += tong_nhan
                    msg += f"<@{uid}>: Đặt **${tong_cuoc}** ➡️ Thắng **${tong_nhan}** 🎉\n"
                else: 
                    msg += f"<@{uid}>: Đặt **${tong_cuoc}** ➡️ Trắng tay 😢\n"
                    
        save_db(db)
        await interaction.edit_original_response(embed=discord.Embed(title="🎲 BÀN ĐÃ ĐÓNG", description=msg, color=discord.Color.gold()), view=None)

class BetModal(discord.ui.Modal):
    def __init__(self, animal, emoji, baucua_view):
        super().__init__(title=f"Cược cho {animal.capitalize()} {emoji}")
        self.animal, self.emoji, self.baucua_view = animal, emoji, baucua_view
        self.bet_amount = discord.ui.TextInput(label="Nhập tiền cược:", placeholder="VD: 50", required=True)
        self.add_item(self.bet_amount)

    async def on_submit(self, interaction: discord.Interaction):
        try: amount = int(self.bet_amount.value)
        except ValueError: return await interaction.response.send_message("❌ Chỉ được nhập số!", ephemeral=True)
        
        if amount <= 0: return await interaction.response.send_message("❌ Số tiền cược phải lớn hơn 0!", ephemeral=True)

        db, uid = load_db(), str(interaction.user.id)
        if uid not in db["users"]: return await interaction.response.send_message("❌ Bạn chưa `/link` tài khoản!", ephemeral=True)
        if db["users"][uid].get("balance", 0) < amount: return await interaction.response.send_message("❌ Không đủ tiền trong ví!", ephemeral=True)
            
        db["users"][uid]["balance"] -= amount
        save_db(db)
        
        if uid not in self.baucua_view.bets: self.baucua_view.bets[uid] = []
        self.baucua_view.bets[uid].append({"animal": self.animal, "amount": amount})
        await interaction.response.send_message(f"✅ Đã cược **${amount}** vào **{self.animal.capitalize()}** {self.emoji}", ephemeral=True)

# ====================================================================
# --- PHẦN 4: SETUP BOT & BACKUP BẤT TỬ ---
# ====================================================================
class MyBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self): await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user.name} ĐÃ SẴN SÀNG TRÊN RENDER!')
    
    # KHÔI PHỤC DỮ LIỆU TỪ BACKUP
    if BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            async for msg in channel.history(limit=10):
                if msg.author == bot.user and msg.attachments:
                    attachment = msg.attachments[0]
                    if attachment.filename == DB_FILE:
                        content = await attachment.read()
                        try:
                            json.loads(content.decode('utf-8'))
                            with open(DB_FILE, 'wb') as f:
                                f.write(content)
                            print("☁️ Đã tải và khôi phục dữ liệu từ Backup thành công!")
                            break 
                        except Exception:
                            print("⚠️ File backup mới nhất bị lỗi, đang thử tìm bản cũ hơn...")
        except Exception as e:
            print(f"Lỗi khôi phục data: {e}")

    if BACKUP_CHANNEL_ID and not auto_backup_task.is_running(): 
        auto_backup_task.start()
    await bot.change_presence(activity=discord.Game(name="/noitu | /baucua | /daily"))

@tasks.loop(minutes=5)
async def auto_backup_task():
    global data_changed
    if data_changed and BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            await channel.purge(limit=50, check=lambda m: m.author == bot.user)
            now_vn = datetime.utcnow() + timedelta(hours=7)
            await channel.send(f"📦 **BACKUP AUTO** ({now_vn.strftime('%H:%M - %d/%m/%Y')}):", file=discord.File(DB_FILE))
            data_changed = False
        except Exception as e: 
            print(f"Lỗi gửi backup: {e}")

# ====================================================================
# --- PHẦN 5: XỬ LÝ GAME NỐI TỪ (ON_MESSAGE) ---
# ====================================================================
@bot.event
async def on_message(message):
    global game_noitu
    if message.author.bot: return

    if message.channel.id == NOITU_CHANNEL_ID:
        text = message.content.lower().strip()
        
        # LỆNH ĐẦU HÀNG /STOP
        if text == "/stop":
            if game_noitu.last_player_id:
                winner_id = game_noitu.last_player_id
                db = load_db()
                
                # Thưởng cơ bản 50$ + bonus nếu chuỗi dài
                bonus = (game_noitu.streak // 5) * 10
                total_reward = 50 + bonus
                
                if winner_id in db["users"]:
                    db["users"][winner_id]["balance"] += total_reward
                    save_db(db)
                
                embed = discord.Embed(title="🛑 TRÒ CHƠI ĐÃ DỪNG!", color=discord.Color.red())
                embed.add_field(name="🏆 Người chiến thắng", value=f"<@{winner_id}>", inline=False)
                embed.add_field(name="🔥 Chuỗi đạt được", value=f"**{game_noitu.streak}** từ", inline=True)
                embed.add_field(name="💰 Tiền thưởng", value=f"**${total_reward}**", inline=True)
                await message.channel.send(embed=embed)
            else:
                await message.channel.send(f"🛑 Đã dừng! Từ hiện tại là **'{game_noitu.current_word}'** nhưng chưa ai chơi.")
            
            game_noitu.reset()
            await message.channel.send(f"🔄 **VÒNG MỚI BẮT ĐẦU!** Từ khởi đầu là: **{game_noitu.current_word}**\n*(Mời bạn nối tiếp chữ '{game_noitu.current_word.split()[-1]}')*")
            return

        # LOGIC NỐI TỪ
        words = text.split()
        if len(words) == 2 and text.replace(" ", "").isalpha(): 
            uid = str(message.author.id)
            
            if uid == game_noitu.last_player_id:
                await message.reply("❌ Bạn không thể tự nối tiếp từ của chính mình! Hãy đợi người khác.")
                return
            
            last_syllable = game_noitu.current_word.split()[-1]
            first_syllable = words[0]
            
            if first_syllable == last_syllable:
                # KIỂM TRA TRÙNG TỪ
                if text in game_noitu.used_words:
                    await message.add_reaction("♻️")
                    await message.reply("⚠️ Từ này đã được sử dụng trong vòng này rồi! Vui lòng tìm từ khác.")
                    return

                # NỐI THÀNH CÔNG
                game_noitu.current_word = text
                game_noitu.last_player_id = uid
                game_noitu.used_words.add(text)
                game_noitu.streak += 1
                
                db = load_db()
                # Cứ nối đúng mặc định được $5. Nếu chuỗi >= 10, mỗi từ được $10
                reward_per_word = 10 if game_noitu.streak >= 10 else 5

                if uid in db["users"]:
                    db["users"][uid]["balance"] += reward_per_word
                    save_db(db)
                    await message.add_reaction("✅")
                    
                    # Chúc mừng nếu đạt cột mốc chuỗi
                    if game_noitu.streak % 10 == 0:
                        await message.channel.send(f"🔥 **COMBO X{game_noitu.streak}!** Từ bây giờ phần thưởng tăng lên!\n*(Tiếp tục nối chữ '{game_noitu.current_word.split()[-1]}')*")
                else:
                    await message.reply("❌ Bạn nối đúng nhưng chưa `/link` tài khoản nên không nhận được thưởng!")
            else:
                await message.add_reaction("❌")

    await bot.process_commands(message)

# ====================================================================
# --- PHẦN 6: LỆNH BOT (SLASH COMMANDS) ---
# ====================================================================
@bot.tree.command(name="noitu", description="Kiểm tra thông tin vòng Nối Từ hiện tại.")
async def info_noitu(interaction: discord.Interaction):
    global game_noitu
    embed = discord.Embed(title="🔠 THÔNG TIN NỐI TỪ", color=discord.Color.blue())
    embed.add_field(name="Từ hiện tại", value=f"**{game_noitu.current_word}**", inline=False)
    embed.add_field(name="Gợi ý nối tiếp", value=f"Bắt đầu bằng chữ: **{game_noitu.current_word.split()[-1]}**", inline=False)
    embed.add_field(name="Độ dài chuỗi", value=f"**{game_noitu.streak}** từ", inline=True)
    embed.add_field(name="Người nối cuối", value=f"<@{game_noitu.last_player_id}>" if game_noitu.last_player_id else "Chưa có", inline=True)
    embed.set_footer(text="Gõ /stop trên kênh nối từ để kết thúc vòng và nhận thưởng lớn!")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="link", description="Liên kết tài khoản game Minecraft.")
async def link(interaction: discord.Interaction, mc_name: str):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: 
        db["users"][uid] = {"balance": 0, "mc_name": mc_name}
        save_db(db)
        await interaction.response.send_message(f"✅ Đã liên kết tài khoản game: **{mc_name}** thành công.")
    else: 
        await interaction.response.send_message("❌ Bạn đã liên kết tài khoản rồi!", ephemeral=True)

@bot.tree.command(name="daily", description="Nhận tiền thưởng mỗi ngày.")
async def daily(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Bạn chưa `/link`!", ephemeral=True)
    
    now_vn = datetime.utcnow() + timedelta(hours=7)
    current_date = now_vn.strftime("%Y-%m-%d")
    
    if db["users"][uid].get("last_daily", "") == current_date: 
        return await interaction.response.send_message("⏳ Bạn đã nhận quà hôm nay rồi, hãy quay lại vào sau 00:00 đêm nay!", ephemeral=True)
    
    reward = random.randint(50, 150)
    db["users"][uid]["last_daily"] = current_date
    db["users"][uid]["balance"] = db["users"][uid].get("balance", 0) + reward
    save_db(db)
    
    await interaction.response.send_message(f"🎁 Bạn vừa điểm danh và nhận được **${reward}**.")

@bot.tree.command(name="baucua", description="Tạo sòng Bầu Cua Tôm Cá.")
async def baucua(interaction: discord.Interaction): 
    await interaction.response.send_message(embed=discord.Embed(title="🎪 SÒNG BẦU CUA", description=f"Nhà cái: **{interaction.user.display_name}**\nBấm nút bên dưới để cược!", color=discord.Color.blue()), view=BauCuaView(host_id=interaction.user.id))

@bot.tree.command(name="pay", description="Chuyển tiền cho người chơi khác.")
async def pay(interaction: discord.Interaction, user: discord.Member, amount: int):
    db, uid, target_id = load_db(), str(interaction.user.id), str(user.id)
    
    if uid not in db["users"]: return await interaction.response.send_message("❌ Bạn chưa `/link`!", ephemeral=True)
    if target_id not in db["users"]: return await interaction.response.send_message("❌ Người nhận chưa `/link` tài khoản!", ephemeral=True)
    if uid == target_id: return await interaction.response.send_message("❌ Bạn không thể tự chuyển tiền cho chính mình!", ephemeral=True)
    if amount <= 0 or db["users"][uid].get("balance", 0) < amount:
        return await interaction.response.send_message("❌ Số tiền không hợp lệ hoặc bạn không đủ tiền!", ephemeral=True)
    
    db["users"][uid]["balance"] -= amount
    db["users"][target_id]["balance"] += amount
    save_db(db)
    
    await interaction.response.send_message(f"💸 {interaction.user.mention} đã chuyển **${amount}** cho {user.mention}!")

@bot.tree.command(name="ruttien", description="Rút tiền từ Bot vào game Minecraft.")
async def ruttien(interaction: discord.Interaction, so_tien: int):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Bạn chưa `/link`!", ephemeral=True)
    if so_tien <= 0 or db["users"][uid].get("balance", 0) < so_tien:
        return await interaction.response.send_message("❌ Không đủ tiền hoặc số tiền không hợp lệ!", ephemeral=True)
    
    if not CONSOLE_CHANNEL_ID:
        return await interaction.response.send_message("❌ Kênh Console chưa được thiết lập!", ephemeral=True)

    await interaction.response.defer()

    if SERVER_IP:
        try:
            clean_ip = SERVER_IP.split(":")[0] if ":" in SERVER_IP else SERVER_IP
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.mcsrvstat.us/2/{clean_ip}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if not data.get("online"):
                            return await interaction.followup.send("❌ **SERVER ĐANG TẮT!** Vui lòng mở server trước khi rút tiền để tránh mất oan số dư.", ephemeral=True)
        except Exception as e:
            print(f"Lỗi check API Server: {e}")

    mc_name = db["users"][uid]["mc_name"]
    db["users"][uid]["balance"] -= so_tien
    save_db(db)
    
    try:
        console_channel = await bot.fetch_channel(CONSOLE_CHANNEL_ID)
        await console_channel.send(f"eco give {mc_name} {so_tien}")
        await interaction.followup.send(f"✅ Đã trừ **${so_tien}** trên Discord.\n💸 Tiền đang được chuyển vào game cho nhân vật **{mc_name}**!")
    except Exception as e:
        db["users"][uid]["balance"] += so_tien
        save_db(db)
        await interaction.followup.send(f"❌ Lỗi kết nối tới Console, đã hoàn lại **${so_tien}** vào ví.", ephemeral=True)

@bot.tree.command(name="vi", description="Xem số dư tài khoản của bạn.")
async def vi(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Bạn cần dùng lệnh `/link` trước!", ephemeral=True)
    
    u = db["users"][uid]
    embed = discord.Embed(title=f"💳 VÍ TIỀN: {interaction.user.display_name}", color=discord.Color.green())
    embed.add_field(name="👤 Tên Game", value=f"`{u.get('mc_name', 'Unknown')}`", inline=True)
    embed.add_field(name="💰 Số dư", value=f"**${u.get('balance', 0)}**", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="backup", description="[ADMIN] Bắt buộc bot lưu và gửi file backup ngay lập tức.")
@default_permissions(administrator=True)
async def force_backup(interaction: discord.Interaction):
    if not BACKUP_CHANNEL_ID:
        return await interaction.response.send_message("❌ Chưa thiết lập ID Kênh Backup!", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    try:
        channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
        await channel.purge(limit=50, check=lambda m: m.author == bot.user)
        now_vn = datetime.utcnow() + timedelta(hours=7)
        await channel.send(f"🛡️ **BACKUP THỦ CÔNG** ({now_vn.strftime('%H:%M - %d/%m/%Y')}):", file=discord.File(DB_FILE))
        
        global data_changed
        data_changed = False
        await interaction.followup.send("✅ Đã ép bot sao lưu thành công lên kênh Backup!")
    except Exception as e:
        await interaction.followup.send(f"❌ Có lỗi xảy ra: {e}")

# KHỞI CHẠY
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
