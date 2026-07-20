import discord
from discord.ext import commands, tasks
import json
import random
import os
import aiohttp
from flask import Flask
from threading import Thread
from datetime import datetime

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
SERVER_IP = os.environ.get('SERVER_IP', '') # VD: myserver.aternos.me (THÊM BIẾN NÀY LÊN RENDER)

# Lấy ID Kênh từ biến môi trường
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
current_word = "thời tiết" 

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
# --- PHẦN 2: GIAO DIỆN BẦU CUA ---
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
# --- PHẦN 3: SETUP BOT & AUTO RECOVERY ---
# ====================================================================
class MyBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self): await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user.name} ĐÃ SẴN SÀNG!')
    
    if BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            async for msg in channel.history(limit=5):
                if msg.author == bot.user and msg.attachments:
                    attachment = msg.attachments[0]
                    if attachment.filename == DB_FILE:
                        await attachment.save(DB_FILE)
                        print("☁️ Đã tải xuống và khôi phục dữ liệu từ Backup!")
                        break
        except Exception as e:
            print(f"Lỗi khôi phục data: {e}")

    if BACKUP_CHANNEL_ID and not auto_backup_task.is_running(): 
        auto_backup_task.start()
    await bot.change_presence(activity=discord.Game(name="/daily | /pay | /baucua"))

@tasks.loop(minutes=5)
async def auto_backup_task():
    global data_changed
    if data_changed and BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            async for msg in channel.history(limit=10):
                if msg.author == bot.user: await msg.delete()
            await channel.send(f"📦 **BACKUP AUTO** ({datetime.now().strftime('%H:%M')}):", file=discord.File(DB_FILE))
            data_changed = False
        except: pass

# ====================================================================
# --- PHẦN 4: HỆ THỐNG NỐI TỪ KIẾM TIỀN ---
# ====================================================================
@bot.event
async def on_message(message):
    global current_word
    if message.author.bot: return

    if message.channel.id == NOITU_CHANNEL_ID:
        text = message.content.lower().strip()
        words = text.split()
        
        # Đã fix lỗi isalpha() không nhận diện được dấu cách
        if len(words) == 2 and text.replace(" ", "").isalpha(): 
            last_syllable = current_word.split()[-1]
            first_syllable = words[0]
            
            if first_syllable == last_syllable:
                current_word = text
                db = load_db()
                uid = str(message.author.id)
                
                if uid in db["users"]:
                    db["users"][uid]["balance"] += 5
                    save_db(db)
                    await message.add_reaction("✅")
                else:
                    await message.reply("❌ Bạn nối đúng nhưng chưa `/link` tài khoản nên không nhận được thưởng!")
            else:
                await message.add_reaction("❌")

    await bot.process_commands(message)

# ====================================================================
# --- PHẦN 5: LỆNH BOT (SLASH COMMANDS) ---
# ====================================================================
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
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    if db["users"][uid].get("last_daily", "") == current_date: 
        return await interaction.response.send_message("⏳ Bạn đã nhận quà hôm nay rồi, hãy quay lại vào ngày mai!", ephemeral=True)
    
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

    # Đưa bot vào trạng thái suy nghĩ để tránh lỗi Timeout khi gọi API
    await interaction.response.defer()

    # KỂM TRA SERVER ONLINE (Đã tối ưu cho IP có Port)
    if SERVER_IP:
        try:
            # Tách IP và Port nếu người dùng nhập dạng ip:port
            clean_ip = SERVER_IP
            if ":" in SERVER_IP:
                clean_ip = SERVER_IP.split(":")[0]
                
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.mcsrvstat.us/2/{clean_ip}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if not data.get("online"):
                            return await interaction.followup.send("❌ **SERVER ĐANG TẮT!** Vui lòng mở server trước khi rút tiền để tránh mất oan số dư.", ephemeral=True)
        except Exception as e:
            print(f"Lỗi check API Server: {e}")

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

# CHẠY BOT
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
