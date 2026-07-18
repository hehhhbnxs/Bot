import discord
from discord.ext import commands, tasks
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
def home(): return "✅ Bot Aternos V8 (Level, Rương Đồ, Smart Backup) đang chạy!"
def run_web():
    try: app.run(host='0.0.0.0', port=8080)
    except: pass
def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ====================================================================
# --- PHẦN 2: HỆ THỐNG SMART BACKUP & DATABASE ---
# ====================================================================
TOKEN = os.environ.get('DISCORD_TOKEN')
CONSOLE_CHANNEL_ID = int(os.environ.get('CONSOLE_CHANNEL_ID', 0))
BACKUP_CHANNEL_ID = int(os.environ.get('BACKUP_CHANNEL_ID', 0))

DB_FILE = 'users.json'
data_changed = False
USER_PARTY = {}

def load_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_db(data):
    global data_changed
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
        data_changed = True
    except Exception as e: print(f"Lỗi lưu file: {e}")

# Các Boss Thế Giới
BOSSES = [
    {"name": "Ma Vương Râu Trắng 👹", "drop": "Sừng Ma Vương", "drop_price": 200},
    {"name": "Rồng Thần Hủy Diệt 🐉", "drop": "Vảy Rồng Thần", "drop_price": 400},
    {"name": "Titan Hắc Ám 🧟‍♂️", "drop": "Lõi Titan", "drop_price": 300},
    {"name": "Quái Vật Hồ Ness 🦕", "drop": "Mắt Quái Biển", "drop_price": 150}
]

WEAPONS = {
    "Kiếm Gỗ": {"price": 50, "power": 15, "emoji": "🪵", "desc": "Tăng 15 sức mạnh"},
    "Kiếm Sắt": {"price": 150, "power": 30, "emoji": "🗡️", "desc": "Tăng 30 sức mạnh"},
    "Kiếm Kim Cương": {"price": 500, "power": 55, "emoji": "💎", "desc": "Tăng 55 sức mạnh"},
    "Thánh Kiếm Excalibur": {"price": 1500, "power": 120, "emoji": "⚔️", "desc": "Vũ khí huyền thoại (+120 SM)"}
}

# Tính năng thăng cấp
def add_xp(db, uid, amount):
    if uid not in db: return ""
    db[uid]["xp"] = db[uid].get("xp", 0) + amount
    level = db[uid].get("level", 1)
    xp_needed = level * 100
    if db[uid]["xp"] >= xp_needed:
        db[uid]["level"] = level + 1
        db[uid]["xp"] -= xp_needed
        db[uid]["base_power"] = db[uid].get("base_power", 0) + 5
        return f"\n🌟 **THĂNG CẤP!** Bạn đã đạt Level {db[uid]['level']}! Tăng +5 Sức mạnh cơ bản."
    return ""

def get_total_power(db, uid):
    u = db.get(uid, {})
    base = u.get("base_power", 0) + (u.get("level", 1) * 2) # Cấp độ cũng cộng sức mạnh ngầm
    w_power = u.get("power", 0)
    return base + w_power

# ====================================================================
# --- PHẦN 3: GIAO DIỆN & TỔ ĐỘI ---
# ====================================================================
class MoviVaoDoiView(discord.ui.View):
    def __init__(self, leader: discord.Member, target: discord.Member):
        super().__init__(timeout=60)
        self.leader, self.target = leader, target

    @discord.ui.button(label="Đồng ý vào đội", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id: return await interaction.response.send_message("❌ Lời mời không dành cho bạn!", ephemeral=True)
        lid, tid = str(self.leader.id), str(self.target.id)
        if lid not in USER_PARTY: USER_PARTY[lid] = lid
        if len([u for u, p in USER_PARTY.items() if p == lid]) >= 4:
            self.stop(); return await interaction.response.send_message("❌ Đội này đã đầy (Tối đa 4)!", ephemeral=True)
        USER_PARTY[tid] = lid
        await interaction.response.edit_message(content=f"🤝 **{self.target.display_name}** đã gia nhập tổ đội của **{self.leader.display_name}**!", view=None)
        self.stop()

class ShopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    async def buy_weapon(self, interaction, weapon_name):
        db, uid = load_db(), str(interaction.user.id)
        if uid not in db: return await interaction.response.send_message("❌ Chưa `/link`!", ephemeral=True)
        price, power = WEAPONS[weapon_name]["price"], WEAPONS[weapon_name]["power"]
        if db[uid].get("balance", 0) < price: return await interaction.response.send_message(f"❌ Không đủ **${price}**!", ephemeral=True)
        if db[uid].get("power", 0) >= power: return await interaction.response.send_message("❌ Bạn đang có vũ khí mạnh ngang hoặc hơn rồi!", ephemeral=True)
        db[uid]["balance"] -= price
        db[uid]["weapon"], db[uid]["power"] = weapon_name, power
        save_db(db)
        await interaction.response.send_message(f"✅ Đã trang bị **{weapon_name}** {WEAPONS[weapon_name]['emoji']}!", ephemeral=True)

    @discord.ui.button(label="Kiếm Gỗ ($50)", style=discord.ButtonStyle.secondary, emoji="🪵")
    async def btn_wood(self, i, b): await self.buy_weapon(i, "Kiếm Gỗ")
    @discord.ui.button(label="Kiếm Sắt ($150)", style=discord.ButtonStyle.secondary, emoji="🗡️")
    async def btn_iron(self, i, b): await self.buy_weapon(i, "Kiếm Sắt")
    @discord.ui.button(label="Kiếm Kim Cương ($500)", style=discord.ButtonStyle.primary, emoji="💎")
    async def btn_diamond(self, i, b): await self.buy_weapon(i, "Kiếm Kim Cương")
    @discord.ui.button(label="Thánh Kiếm ($1500)", style=discord.ButtonStyle.danger, emoji="⚔️", row=1)
    async def btn_excal(self, i, b): await self.buy_weapon(i, "Thánh Kiếm Excalibur")

# ====================================================================
# --- PHẦN 4: HỆ THỐNG BOT & SLASH COMMANDS ---
# ====================================================================
class MyBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=discord.Intents.default())
    async def setup_hook(self): await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user.name} V8 đã sẵn sàng!')
    # Phục hồi dữ liệu thông minh
    if BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            async for msg in channel.history(limit=10):
                if msg.author == bot.user and msg.attachments and msg.attachments[0].filename == 'users.json':
                    await msg.attachments[0].save(DB_FILE)
                    print("✅ Đã khôi phục dữ liệu từ Đám mây Discord!")
                    break
        except Exception as e: print("Không tìm thấy backup cũ:", e)
        
    if not auto_backup_task.is_running(): auto_backup_task.start()
    await bot.change_presence(activity=discord.Game(name="RPG Mới: /ruongdo & /sanboss"))

@tasks.loop(minutes=3)
async def auto_backup_task():
    global data_changed
    if data_changed and BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            # Xóa TẤT CẢ tin nhắn cũ của bot trong kênh backup để giữ kênh luôn gọn gàng (chỉ để lại file mới nhất)
            async for msg in channel.history(limit=20):
                if msg.author == bot.user: await msg.delete()
            
            # Gửi file mới
            await channel.send(f"☁️ **SMART BACKUP V8** ({time.strftime('%H:%M %d/%m/%Y')}):\n*Chỉ giữ lại bản lưu trữ mới nhất.*", file=discord.File(DB_FILE))
            data_changed = False
        except: pass

# --- KHU VỰC TÀI KHOẢN & NHÂN VẬT ---
@bot.tree.command(name="link", description="Tạo hồ sơ nhân vật (Liên kết tài khoản game).")
async def link(interaction: discord.Interaction, mc_name: str):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db: 
        db[uid] = {"balance": 0, "mc_name": mc_name, "weapon": "Tay không", "power": 0, "level": 1, "xp": 0, "base_power": 0, "inventory": {}}
        save_db(db); await interaction.response.send_message(f"✅ Đã tạo hồ sơ: **{mc_name}**.")
    else: await interaction.response.send_message("❌ Bạn đã có hồ sơ rồi!", ephemeral=True)

@bot.tree.command(name="vi", description="Xem thẻ nhân vật RPG.")
async def vi(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db: return await interaction.response.send_message("❌ Hãy tạo hồ sơ bằng `/link`!", ephemeral=True)
    u = db[uid]
    total_pw = get_total_power(db, uid)
    
    embed = discord.Embed(title=f"📜 THẺ NHÂN VẬT: {interaction.user.display_name}", color=discord.Color.gold())
    embed.add_field(name="🔹 Cấp độ", value=f"**Lv {u.get('level', 1)}** (XP: {u.get('xp', 0)}/{u.get('level', 1)*100})", inline=True)
    embed.add_field(name="💳 Tài sản", value=f"**${u.get('balance', 0)}**", inline=True)
    embed.add_field(name="⚔️ Sức mạnh Tổng", value=f"**{total_pw}**", inline=True)
    embed.add_field(name="🛡️ Vũ khí trang bị", value=f"{u.get('weapon', 'Tay không')} (+{u.get('power', 0)} SM)", inline=False)
    
    inv_count = sum(u.get('inventory', {}).values())
    embed.add_field(name="🎒 Rương đồ", value=f"Đang có {inv_count} vật phẩm. Dùng `/ruongdo` để xem.", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shop", description="Mở cửa hàng vũ khí.")
async def shop(interaction: discord.Interaction):
    embed = discord.Embed(title="🛒 CỬA HÀNG VŨ KHÍ", color=discord.Color.purple())
    for name, data in WEAPONS.items(): embed.add_field(name=f"{data['emoji']} {name} - ${data['price']}", value=f"*{data['desc']}*", inline=False)
    await interaction.response.send_message(embed=embed, view=ShopView())

# --- KHU VỰC RƯƠNG ĐỒ & VẬT PHẨM ---
@bot.tree.command(name="ruongdo", description="Xem các vật phẩm hiếm trong Rương.")
async def ruongdo(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db: return await interaction.response.send_message("❌ Lỗi hồ sơ!", ephemeral=True)
    inventory = db[uid].get("inventory", {})
    if not inventory: return await interaction.response.send_message("🎒 Rương đồ của bạn đang trống rỗng!")
    
    msg = "🎒 **RƯƠNG ĐỒ CỦA BẠN:**\n"
    for item, qty in inventory.items():
        if qty > 0: msg += f"- **{item}**: {qty} cái\n"
    msg += "\n*Mẹo: Dùng `/banvatpham` để bán lấy tiền mặt.*"
    await interaction.response.send_message(msg)

@bot.tree.command(name="banvatpham", description="Bán vật phẩm hiếm để lấy tiền.")
async def banvatpham(interaction: discord.Interaction, ten_vat_pham: str, so_luong: int):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db or so_luong <= 0: return await interaction.response.send_message("❌ Lỗi!", ephemeral=True)
    inventory = db[uid].get("inventory", {})
    
    if inventory.get(ten_vat_pham, 0) < so_luong:
        return await interaction.response.send_message(f"❌ Bạn không đủ **{ten_vat_pham}** trong rương!", ephemeral=True)
        
    # Tìm giá vật phẩm (từ danh sách Boss rớt)
    item_price = 50 # Mặc định nếu không tìm thấy
    for b in BOSSES:
        if b["drop"] == ten_vat_pham: item_price = b["drop_price"]

    earned = item_price * so_luong
    db[uid]["inventory"][ten_vat_pham] -= so_luong
    if db[uid]["inventory"][ten_vat_pham] == 0: del db[uid]["inventory"][ten_vat_pham]
    db[uid]["balance"] += earned
    save_db(db)
    
    await interaction.response.send_message(f"💸 Thương gia đã mua **{so_luong}x {ten_vat_pham}** của bạn với giá **${earned}**!")

# --- KHU VỰC TỔ ĐỘI & ĐÁNH BOSS ---
@bot.tree.command(name="lapdoi", description="Mời người chơi khác vào tổ đội.")
async def lapdoi(interaction: discord.Interaction, nguoi_choi: discord.Member):
    lid, tid = str(interaction.user.id), str(nguoi_choi.id)
    if lid == tid: return await interaction.response.send_message("❌ Lỗi!", ephemeral=True)
    view = MoviVaoDoiView(interaction.user, nguoi_choi)
    await interaction.response.send_message(f"🚩 **{interaction.user.display_name}** đang mời **{nguoi_choi.mention}** vào Tổ Đội!", view=view)

@bot.tree.command(name="thongtindoi", description="Xem thông tin Tổ Đội.")
async def thongtindoi(interaction: discord.Interaction):
    uid, db = str(interaction.user.id), load_db()
    if uid not in USER_PARTY: return await interaction.response.send_message("❌ Bạn chưa vào đội!", ephemeral=True)
    party_id = USER_PARTY[uid]
    members = [u for u, p in USER_PARTY.items() if p == party_id]
    
    msg = f"🛡️ **THÔNG TIN TỔ ĐỘI**\n\n"
    total_pw = 0
    for m in members:
        pw = get_total_power(db, m)
        total_pw += pw
        msg += f"👤 <@{m}> (Lv {db.get(m,{}).get('level',1)}) - Lực chiến: {pw}\n"
    msg += f"\n🔥 **TỔNG LỰC CHIẾN ĐỘI:** {total_pw}"
    await interaction.response.send_message(msg)

@bot.tree.command(name="sanboss", description="Cùng Tổ đội đánh Boss (Phí: $50/đội).")
async def sanboss(interaction: discord.Interaction):
    uid, db = str(interaction.user.id), load_db()
    if uid not in USER_PARTY or USER_PARTY[uid] != uid: return await interaction.response.send_message("❌ Chỉ Đội trưởng được dùng!", ephemeral=True)
    if db.get(uid, {}).get("balance", 0) < 50: return await interaction.response.send_message("❌ Cần $50 phí mở cổng!", ephemeral=True)
        
    members = [u for u, p in USER_PARTY.items() if p == uid]
    total_power = sum(get_total_power(db, m) for m in members)
    db[uid]["balance"] -= 50
    
    boss = random.choice(BOSSES)
    win_chance = min(95, 10 + int(total_power * 0.5)) # Độ khó cao hơn xíu
    
    if random.randint(1, 100) <= win_chance:
        cash_reward = random.randint(100, 200)
        xp_reward = random.randint(30, 80)
        
        msg = f"🎉 **CHIẾN THẮNG!** Đội bạn đã tiêu diệt **{boss['name']}**!\n💰 Mỗi người nhận: **${cash_reward}** & **{xp_reward} XP**\n"
        
        # Xử lý phần thưởng cho từng thành viên
        for m in members:
            db[m]["balance"] += cash_reward
            levelup_msg = add_xp(db, m, xp_reward)
            msg += levelup_msg
            
            # Tỷ lệ 40% rơi vật phẩm hiếm cho mỗi người
            if random.random() < 0.40:
                if "inventory" not in db[m]: db[m]["inventory"] = {}
                db[m]["inventory"][boss["drop"]] = db[m]["inventory"].get(boss["drop"], 0) + 1
                msg += f"\n🎁 <@{m}> nhặt được 1x **{boss['drop']}**!"
    else:
        msg = f"💀 **THẤT BẠI!** **{boss['name']}** quá mạnh. Cả đội tử trận và mất $50 phí mở cổng."
        
    save_db(db)
    await interaction.response.send_message(msg)

@bot.tree.command(name="santhu", description="Đi săn cá nhân kiếm XP và Tiền (Phí $10).")
async def santhu(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db or db[uid].get("balance", 0) < 10: return await interaction.response.send_message("❌ Cần $10!", ephemeral=True)
    db[uid]["balance"] -= 10
    
    pw = get_total_power(db, uid)
    if random.randint(1, 100) <= min(90, 30 + pw):
        r_cash, r_xp = random.randint(20, 50), random.randint(15, 30)
        db[uid]["balance"] += r_cash
        lvl_msg = add_xp(db, uid, r_xp)
        msg = f"🎉 Bạn hạ quái thú! Nhận **${r_cash}** và **{r_xp} XP**.{lvl_msg}"
    else: msg = f"💀 Quái vật đánh bại bạn. Mất trắng $10!"
    
    save_db(db); await interaction.response.send_message(msg)

@bot.tree.command(name="daily", description="Điểm danh.")
async def daily(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db: return await interaction.response.send_message("❌ Chưa `/link`!", ephemeral=True)
    if time.time() - db[uid].get("last_daily", 0) < 86400: return await interaction.response.send_message("⏳ Hôm nay nhận rồi!", ephemeral=True)
    reward = random.randint(20, 50)
    db[uid]["last_daily"], db[uid]["balance"] = time.time(), db[uid].get("balance", 0) + reward
    save_db(db); await interaction.response.send_message(f"🎁 Điểm danh thành công! Nhận **${reward}**.")

@bot.tree.command(name="ruttien", description="Rút tiền vào Game.")
async def ruttien(interaction: discord.Interaction, so_tien: int):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db or so_tien <= 0 or db[uid].get("balance", 0) < so_tien: return await interaction.response.send_message("❌ Không đủ tiền!", ephemeral=True)
    console = bot.get_channel(CONSOLE_CHANNEL_ID) or await bot.fetch_channel(CONSOLE_CHANNEL_ID)
    if console:
        db[uid]["balance"] -= so_tien; save_db(db)
        await console.send(f'eco give {db[uid]["mc_name"]} {so_tien}')
        await interaction.response.send_message(f"💸 Đã rút **${so_tien}** vào nhân vật **{db[uid]['mc_name']}** trong game.")
    else: await interaction.response.send_message("❌ Lỗi kết nối Server Minecraft.", ephemeral=True)

# ====================================================================
# --- KHỞI ĐỘNG ---
# ====================================================================
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
