import discord
from discord.ext import commands, tasks
import json
import random
import time
import os
from flask import Flask
from threading import Thread
from datetime import datetime # Dùng cho Daily

# ====================================================================
# --- CẤU HÌNH WEB SERVER (GIỮ BOT ONLINE) ---
# ====================================================================
app = Flask('')
@app.route('/')
def home(): return "✅ Bot Aternos V9 (RPG, Queue, Smart Backup) đang chạy!"
def run_web():
    try: app.run(host='0.0.0.0', port=8080)
    except: pass
def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ====================================================================
# --- CẤU HÌNH, DATABASE & HÀNG ĐỢI RÚT TIỀN ---
# ====================================================================
TOKEN = os.environ.get('DISCORD_TOKEN')
CONSOLE_CHANNEL_ID = int(os.environ.get('CONSOLE_CHANNEL_ID', 0))
BACKUP_CHANNEL_ID = int(os.environ.get('BACKUP_CHANNEL_ID', 0))

DB_FILE = 'users.json'
data_changed = False
USER_PARTY = {}

def load_db():
    if not os.path.exists(DB_FILE): return {"users": {}, "pending": []}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "users" not in data: data = {"users": data, "pending": []}
            return data
    except: return {"users": {}, "pending": []}

def save_db(data):
    global data_changed
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
        data_changed = True
    except Exception as e: print(f"Lỗi lưu file: {e}")

async def process_pending_withdrawals(bot_instance):
    db = load_db()
    if not db.get("pending"): return
    try:
        console = bot_instance.get_channel(CONSOLE_CHANNEL_ID) or await bot_instance.fetch_channel(CONSOLE_CHANNEL_ID)
        if not console: return
        print("🔄 Đang xử lý lệnh rút tiền chờ...")
        for item in db["pending"][:]:
            await console.send(f'eco give {item["mc_name"]} {item["amount"]}')
            db["pending"].remove(item)
        save_db(db)
        print("✅ Đã gửi hết lệnh chờ.")
    except Exception as e: print(f"❌ Lỗi gửi hàng đợi: {e}")

# ====================================================================
# --- HỆ THỐNG RPG & CƠ CHẾ ---
# ====================================================================
BOSSES = [
    {"name": "Ma Vương Râu Trắng 👹", "drop": "Sừng Ma Vương", "drop_price": 200},
    {"name": "Rồng Thần Hủy Diệt 🐉", "drop": "Vảy Rồng Thần", "drop_price": 400},
    {"name": "Titan Hắc Ám 🧟‍♂️", "drop": "Lõi Titan", "drop_price": 300},
    {"name": "Quái Vật Hồ Ness 🦕", "drop": "Mắt Quái Biển", "drop_price": 150}
]

WEAPONS = {
    "Kiếm Gỗ": {"price": 50, "power": 15, "emoji": "🪵"},
    "Kiếm Sắt": {"price": 150, "power": 30, "emoji": "🗡️"},
    "Kiếm Kim Cương": {"price": 500, "power": 55, "emoji": "💎"},
    "Thánh Kiếm Excalibur": {"price": 1500, "power": 120, "emoji": "⚔️"}
}

def get_total_power(db, uid):
    u = db["users"].get(uid, {})
    return u.get("base_power", 0) + (u.get("level", 1) * 2) + u.get("power", 0)

# ====================================================================
# --- CÁC GIAO DIỆN (VIEW) ---
# ====================================================================
class ShopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    async def buy(self, i, name):
        db, uid = load_db(), str(i.user.id)
        if uid not in db["users"]: return await i.response.send_message("❌ Chưa /link", ephemeral=True)
        w = WEAPONS[name]
        if db["users"][uid]["balance"] < w["price"]: return await i.response.send_message("❌ Không đủ tiền!", ephemeral=True)
        db["users"][uid]["balance"] -= w["price"]
        db["users"][uid]["weapon"], db["users"][uid]["power"] = name, w["power"]
        save_db(db); await i.response.send_message(f"✅ Đã mua {name}!", ephemeral=True)
    
    @discord.ui.button(label="Kiếm Gỗ", style=discord.ButtonStyle.secondary)
    async def b1(self, i, b): await self.buy(i, "Kiếm Gỗ")
    @discord.ui.button(label="Kiếm Sắt", style=discord.ButtonStyle.secondary)
    async def b2(self, i, b): await self.buy(i, "Kiếm Sắt")
    @discord.ui.button(label="Kiếm KC", style=discord.ButtonStyle.primary)
    async def b3(self, i, b): await self.buy(i, "Kiếm Kim Cương")
    @discord.ui.button(label="Excalibur", style=discord.ButtonStyle.danger)
    async def b4(self, i, b): await self.buy(i, "Thánh Kiếm Excalibur")

# ====================================================================
# --- BOT SETUP & EVENTS ---
# ====================================================================
class MyBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=discord.Intents.default())
    async def setup_hook(self): await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user.name} V9 ĐÃ SẴN SÀNG!')
    if BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            async for msg in channel.history(limit=5):
                if msg.author == bot.user and msg.attachments:
                    await msg.attachments[0].save(DB_FILE); break
        except: pass
    await process_pending_withdrawals(bot)
    if not auto_backup_task.is_running(): auto_backup_task.start()

@tasks.loop(minutes=3)
async def auto_backup_task():
    global data_changed
    if data_changed and BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            async for msg in channel.history(limit=5):
                if msg.author == bot.user: await msg.delete()
            await channel.send("☁️ Backup:", file=discord.File(DB_FILE))
            data_changed = False
        except: pass

# ====================================================================
# --- CÁC LỆNH SLASH COMMANDS ---
# ====================================================================
@bot.tree.command(name="link", description="Đăng ký hồ sơ")
async def link(interaction: discord.Interaction, mc_name: str):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]:
        db["users"][uid] = {"balance": 0, "mc_name": mc_name, "weapon": "Tay không", "power": 0, "level": 1, "xp": 0, "base_power": 0, "inventory": {}, "last_daily": ""}
        save_db(db); await interaction.response.send_message("✅ Tạo hồ sơ thành công!")
    else: await interaction.response.send_message("❌ Bạn đã có hồ sơ!", ephemeral=True)

@bot.tree.command(name="daily", description="Nhận quà mỗi ngày")
async def daily(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Chưa /link", ephemeral=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    if db["users"][uid].get("last_daily") == today:
        return await interaction.response.send_message("⏳ Đã nhận rồi, mai quay lại nhé!", ephemeral=True)
    
    reward = random.randint(20, 50)
    db["users"][uid]["last_daily"] = today
    db["users"][uid]["balance"] += reward
    save_db(db)
    await interaction.response.send_message(f"🎁 Nhận được **${reward}**. Hẹn gặp lại ngày mai!")

@bot.tree.command(name="pay", description="Chuyển tiền cho người khác")
async def pay(interaction: discord.Interaction, nguoi_nhan: discord.Member, so_tien: int):
    db = load_db()
    uid, tid = str(interaction.user.id), str(nguoi_nhan.id)
    if uid not in db["users"] or tid not in db["users"]: return await interaction.response.send_message("❌ User chưa /link", ephemeral=True)
    if so_tien <= 0 or db["users"][uid]["balance"] < so_tien: return await interaction.response.send_message("❌ Số tiền không hợp lệ!", ephemeral=True)
    db["users"][uid]["balance"] -= so_tien
    db["users"][tid]["balance"] += so_tien
    save_db(db)
    await interaction.response.send_message(f"💸 Đã chuyển **${so_tien}** cho {nguoi_nhan.mention}")

@bot.tree.command(name="ruttien", description="Rút tiền vào game")
async def ruttien(interaction: discord.Interaction, so_tien: int):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"] or db["users"][uid]["balance"] < so_tien: return await interaction.response.send_message("❌ Không đủ tiền!", ephemeral=True)
    db["users"][uid]["balance"] -= so_tien
    db["pending"].append({"mc_name": db["users"][uid]["mc_name"], "amount": so_tien})
    save_db(db)
    await interaction.response.send_message("✅ Lệnh rút tiền đã vào hàng đợi, sẽ gửi ngay khi server mở!")
    await process_pending_withdrawals(bot)

@bot.tree.command(name="vi", description="Xem thông tin")
async def vi(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Chưa /link", ephemeral=True)
    u = db["users"][uid]
    await interaction.response.send_message(f"📜 {interaction.user.name}\n💰 Tiền: ${u['balance']}\n⚔️ Sức mạnh: {get_total_power(db, uid)}\n🎒 Đồ: {list(u['inventory'].keys())}")

@bot.tree.command(name="shop", description="Mua vũ khí")
async def shop(interaction: discord.Interaction):
    await interaction.response.send_message("🛒 Chọn vũ khí:", view=ShopView())

# ====================================================================
# --- CHẠY BOT ---
# ====================================================================
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
