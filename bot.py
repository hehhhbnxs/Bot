import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import random
import time
import os
from flask import Flask
from threading import Thread

# ====================================================================
# --- PHẦN 1: WEB SERVER GIỮ BOT ONLINE (RENDER) ---
# ====================================================================
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot Aternos V4 (Auto Backup) đang chạy!"

def run_web():
    try:
        app.run(host='0.0.0.0', port=8080)
    except:
        pass

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ====================================================================
# --- PHẦN 2: CẤU HÌNH & DATABASE ---
# ====================================================================
TOKEN = os.environ.get('DISCORD_TOKEN')
CONSOLE_CHANNEL_ID_STR = os.environ.get('CONSOLE_CHANNEL_ID')
BACKUP_CHANNEL_ID_STR = os.environ.get('BACKUP_CHANNEL_ID') # ID Kênh lưu dữ liệu

try:
    CONSOLE_CHANNEL_ID = int(CONSOLE_CHANNEL_ID_STR) if CONSOLE_CHANNEL_ID_STR else 0
    BACKUP_CHANNEL_ID = int(BACKUP_CHANNEL_ID_STR) if BACKUP_CHANNEL_ID_STR else 0
except ValueError:
    CONSOLE_CHANNEL_ID = 0
    BACKUP_CHANNEL_ID = 0

DB_FILE = 'users.json'
data_changed = False # Biến theo dõi xem dữ liệu có thay đổi không để backup

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_db(data):
    global data_changed
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        data_changed = True # Đánh dấu là tiền đã thay đổi, cần backup
    except Exception as e:
        print(f"Lỗi lưu file: {e}")

# ====================================================================
# --- PHẦN 3: BẢNG NHẬP SỐ TIỀN (MODAL) ---
# ====================================================================
class BetModal(discord.ui.Modal):
    def __init__(self, animal: str, emoji: str, baucua_view):
        super().__init__(title=f"Cược cho {animal.capitalize()} {emoji}")
        self.animal = animal
        self.emoji = emoji
        self.baucua_view = baucua_view

        self.bet_amount = discord.ui.TextInput(
            label="Nhập số tiền muốn cược:",
            placeholder="Ví dụ: 50",
            required=True,
            max_length=10
        )
        self.add_item(self.bet_amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.bet_amount.value)
        except ValueError:
            await interaction.response.send_message("❌ Lỗi: Vui lòng chỉ nhập số (Ví dụ: 50)!", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("❌ Số tiền cược phải lớn hơn 0!", ephemeral=True)
            return

        db = load_db()
        uid = str(interaction.user.id)
        
        if uid not in db:
            await interaction.response.send_message("❌ Bạn chưa `/link` tài khoản!", ephemeral=True)
            return
            
        user_bal = db[uid].get("balance", 0)
        if user_bal < amount:
            await interaction.response.send_message(f"❌ Bạn chỉ có **${user_bal}** trong Ví. Không đủ ${amount} để cược!", ephemeral=True)
            return
            
        db[uid]["balance"] -= amount
        save_db(db)
        
        if uid not in self.baucua_view.bets:
            self.baucua_view.bets[uid] = []
        self.baucua_view.bets[uid].append({"animal": self.animal, "amount": amount})
        
        await interaction.response.send_message(f"✅ Bạn đã cược **${amount}** vào con **{self.animal.capitalize()}** {self.emoji} (Đã trừ tiền trong Ví)", ephemeral=True)

# ====================================================================
# --- PHẦN 4: BÀN BẦU CUA ---
# ====================================================================
class BauCuaView(discord.ui.View):
    def __init__(self, host_id):
        super().__init__(timeout=180)
        self.host_id = host_id
        self.bets = {} 
        self.message = None

    async def prompt_bet(self, interaction: discord.Interaction, choice: str, emoji: str):
        modal = BetModal(animal=choice, emoji=emoji, baucua_view=self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Bầu", style=discord.ButtonStyle.secondary, emoji="🥒")
    async def btn_bau(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.prompt_bet(interaction, "bầu", "🥒")

    @discord.ui.button(label="Cua", style=discord.ButtonStyle.secondary, emoji="🦀")
    async def btn_cua(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.prompt_bet(interaction, "cua", "🦀")

    @discord.ui.button(label="Tôm", style=discord.ButtonStyle.secondary, emoji="🦐")
    async def btn_tom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.prompt_bet(interaction, "tôm", "🦐")

    @discord.ui.button(label="Cá", style=discord.ButtonStyle.secondary, emoji="🐟", row=1)
    async def btn_ca(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.prompt_bet(interaction, "cá", "🐟")

    @discord.ui.button(label="Gà", style=discord.ButtonStyle.secondary, emoji="🐔", row=1)
    async def btn_ga(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.prompt_bet(interaction, "gà", "🐔")

    @discord.ui.button(label="Nai", style=discord.ButtonStyle.secondary, emoji="🦌", row=1)
    async def btn_nai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.prompt_bet(interaction, "nai", "🦌")

    @discord.ui.button(label="🎲 CHỐT SỔ & LẮC", style=discord.ButtonStyle.danger, row=2)
    async def btn_roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ Chỉ người tạo bàn mới được quyền chốt sổ!", ephemeral=True)
            return

        self.stop()
        
        linh_vat = ['bầu', 'cua', 'tôm', 'cá', 'gà', 'nai']
        ket_qua = [random.choice(linh_vat) for _ in range(3)]
        ket_qua_str = " - ".join([x.capitalize() for x in ket_qua])
        
        db = load_db()
        msg_result = f"🎲 **KẾT QUẢ XÚC XẮC:** [ **{ket_qua_str}** ]\n\n**BẢNG TRẢ THƯỞNG:**\n"
        
        if not self.bets:
            msg_result += "Không có ai đặt cược cả!"
        else:
            for uid, user_bets in self.bets.items():
                tong_nhan = 0
                tong_cuoc = sum(b['amount'] for b in user_bets)
                
                for b in user_bets:
                    so_lan_xuat_hien = ket_qua.count(b['animal'])
                    if so_lan_xuat_hien > 0:
                        tong_nhan += b['amount'] + (b['amount'] * so_lan_xuat_hien)
                
                if tong_nhan > 0:
                    db[uid]["balance"] += tong_nhan
                    msg_result += f"<@{uid}>: Đặt **${tong_cuoc}** ➡️ Nhận về **${tong_nhan}** 🎉\n"
                else:
                    msg_result += f"<@{uid}>: Thua sạch **${tong_cuoc}** cược 😢\n"

        save_db(db)
        
        embed = discord.Embed(title="🎲 BÀN BẦU CUA ĐÃ ĐÓNG", description=msg_result, color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_timeout(self):
        db = load_db()
        for uid, user_bets in self.bets.items():
            for b in user_bets:
                db[uid]["balance"] += b['amount']
        save_db(db)
        if self.message:
            try:
                await self.message.edit(content="⏳ Bàn đã hết hạn! Tiền cược đã được hoàn trả.", view=None)
            except:
                pass

# ====================================================================
# --- PHẦN 5: LỆNH SLASH & HỆ THỐNG BACKUP AUTO ---
# ====================================================================
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
    
    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user.name} V4 đã sẵn sàng!')
    
    # --- KHÔI PHỤC DỮ LIỆU TỪ DISCORD ---
    if BACKUP_CHANNEL_ID:
        try:
            backup_channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            if backup_channel:
                async for message in backup_channel.history(limit=5):
                    if message.author == bot.user and message.attachments:
                        attachment = message.attachments[0]
                        if attachment.filename == 'users.json':
                            await attachment.save(DB_FILE)
                            print("☁️ Đã khôi phục dữ liệu tiền từ Discord thành công!")
                            break
        except Exception as e:
            print(f"⚠️ Không thể khôi phục dữ liệu: {e}")

    # Bật tính năng auto backup
    if not auto_backup_task.is_running():
        auto_backup_task.start()
        
    await bot.change_presence(activity=discord.Game(name="Bầu Cua | /help"))

# Vòng lặp backup lên Discord mỗi 1 phút
@tasks.loop(minutes=1)
async def auto_backup_task():
    global data_changed
    if data_changed and BACKUP_CHANNEL_ID:
        try:
            backup_channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            if backup_channel:
                # Gửi file mới lên
                new_msg = await backup_channel.send("🔄 Bản sao lưu dữ liệu tự động:", file=discord.File(DB_FILE))
                # Xóa các file cũ để đỡ rác kênh
                async for message in backup_channel.history(limit=10):
                    if message.author == bot.user and message.id != new_msg.id:
                        await message.delete()
                data_changed = False # Reset cờ
        except Exception as e:
            pass

@bot.tree.command(name="link", description="Liên kết tài khoản game Minecraft của bạn.")
async def link(interaction: discord.Interaction, mc_name: str):
    db = load_db()
    uid = str(interaction.user.id)
    old_bal = db[uid]["balance"] if uid in db else 0
    old_daily = db[uid]["last_daily"] if uid in db else 0
    db[uid] = {"mc_name": mc_name, "last_daily": old_daily, "balance": old_bal}
    save_db(db)
    await interaction.response.send_message(f"✅ Đã liên kết tài khoản với game: **{mc_name}**")

@bot.tree.command(name="daily", description="Nhận tiền miễn phí mỗi ngày vào Ví Discord.")
async def daily(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    if uid not in db:
        await interaction.response.send_message("❌ Bạn chưa `/link` tài khoản!", ephemeral=True)
        return

    current_time = time.time()
    last_daily = db[uid].get("last_daily", 0)
    if current_time - last_daily < 86400: 
        await interaction.response.send_message("⏳ Bạn đã nhận quà hôm nay rồi!", ephemeral=True)
        return
        
    reward = random.randint(5, 30) 
    db[uid]["last_daily"] = current_time
    db[uid]["balance"] = db[uid].get("balance", 0) + reward
    save_db(db)
    await interaction.response.send_message(f"🎁 Đã nhận **${reward}** vào Ví Discord. Hiện có: **${db[uid]['balance']}**.")

@bot.tree.command(name="vi", description="Xem số dư trong Ví Discord của bạn.")
async def vi(interaction: discord.Interaction):
    db = load_db()
    uid = str(interaction.user.id)
    if uid not in db:
        await interaction.response.send_message("❌ Bạn chưa `/link` tài khoản!", ephemeral=True)
        return
    await interaction.response.send_message(f"💳 Ví Discord của bạn có: **${db[uid].get('balance', 0)}**")

@bot.tree.command(name="ruttien", description="Rút tiền từ Ví Discord vào Game Minecraft.")
async def ruttien(interaction: discord.Interaction, so_tien: int):
    db = load_db()
    uid = str(interaction.user.id)
    
    if uid not in db:
        await interaction.response.send_message("❌ Bạn chưa `/link` tài khoản!", ephemeral=True)
        return
        
    if so_tien <= 0:
        await interaction.response.send_message("❌ Số tiền muốn rút phải lớn hơn 0!", ephemeral=True)
        return

    user_bal = db[uid].get("balance", 0)
    if user_bal < so_tien:
        await interaction.response.send_message(f"❌ Trong Ví của bạn chỉ có **${user_bal}**. Không đủ để rút!", ephemeral=True)
        return

    console_channel = bot.get_channel(CONSOLE_CHANNEL_ID)
    if not console_channel:
        console_channel = await bot.fetch_channel(CONSOLE_CHANNEL_ID)

    if console_channel:
        mc_name = db[uid]["mc_name"]
        db[uid]["balance"] -= so_tien
        save_db(db)
        
        await console_channel.send(f'eco give {mc_name} {so_tien}')
        await interaction.response.send_message(f"💸 Đã rút **${so_tien}** vào nhân vật **{mc_name}** trong game.")
    else:
        await interaction.response.send_message("❌ Lỗi: Không thể kết nối với Server Minecraft.", ephemeral=True)

@bot.tree.command(name="baucua", description="Tạo bàn Bầu Cua Tôm Cá.")
async def baucua(interaction: discord.Interaction):
    view = BauCuaView(host_id=interaction.user.id)
    embed = discord.Embed(title="🎪 BÀN BẦU CUA TÔM CÁ 🎪", color=discord.Color.blue())
    embed.description = f"Chủ bàn: **{interaction.user.display_name}**\n\n*Nhấn vào con vật để nhập số tiền cược! Bạn có thể cược nhiều con khác nhau.*"
    
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()

# ====================================================================
# --- KHỞI ĐỘNG ---
# ====================================================================
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Lỗi: Chưa cấu hình DISCORD_TOKEN.")
    else:
        keep_alive()
        bot.run(TOKEN)
