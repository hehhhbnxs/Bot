import discord
from discord.ext import commands, tasks
import json
import random
import os
from flask import Flask
from threading import Thread
from datetime import datetime

# ====================================================================
# --- PHẦN 1: WEB SERVER & CONFIG TÙY CHỈNH ---
# ====================================================================
app = Flask('')
@app.route('/')
def home(): 
    return "✅ Bot Aternos V11 (Full RPG, Debt, Party) đang chạy!"

def run_web():
    try: app.run(host='0.0.0.0', port=8080)
    except: pass

def keep_alive():
    t = Thread(target=run_web)
    t.start()

TOKEN = os.environ.get('DISCORD_TOKEN')

# Lấy ID Kênh từ biến môi trường (Nếu có)
try:
    CONSOLE_CHANNEL_ID = int(os.environ.get('CONSOLE_CHANNEL_ID', 0))
    BACKUP_CHANNEL_ID = int(os.environ.get('BACKUP_CHANNEL_ID', 0))
except ValueError:
    CONSOLE_CHANNEL_ID = 0
    BACKUP_CHANNEL_ID = 0

DB_FILE = 'users.json'
data_changed = False
USER_PARTY = {} # Quản lý tổ đội (Lưu trữ tạm thời trên RAM)

# --- QUẢN LÝ DATABASE (JSON) ---
def load_db():
    if not os.path.exists(DB_FILE): 
        return {"users": {}, "pending": []}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "users" not in data: data = {"users": data, "pending": []}
            return data
    except: 
        return {"users": {}, "pending": []}

def save_db(data):
    global data_changed
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f: 
            json.dump(data, f, indent=4, ensure_ascii=False)
        data_changed = True
    except Exception as e: 
        print(f"Lỗi lưu file: {e}")

async def process_pending_withdrawals(bot_instance):
    if not CONSOLE_CHANNEL_ID: return
    db = load_db()
    if not db.get("pending"): return
    try:
        console = bot_instance.get_channel(CONSOLE_CHANNEL_ID) or await bot_instance.fetch_channel(CONSOLE_CHANNEL_ID)
        if not console: return
        for item in db["pending"][:]:
            await console.send(f'eco give {item["mc_name"]} {item["amount"]}')
            db["pending"].remove(item)
        save_db(db)
    except Exception as e: 
        print(f"❌ Lỗi gửi hàng đợi: {e}")

# ====================================================================
# --- PHẦN 2: CƠ CHẾ RPG, VŨ KHÍ, QUÁI & NỢ NẦN ---
# ====================================================================
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

def add_xp(db, uid, amount):
    if uid not in db["users"]: return ""
    db["users"][uid]["xp"] = db["users"][uid].get("xp", 0) + amount
    level = db["users"][uid].get("level", 1)
    xp_needed = level * 100
    if db["users"][uid]["xp"] >= xp_needed:
        db["users"][uid]["level"] = level + 1
        db["users"][uid]["xp"] -= xp_needed
        db["users"][uid]["base_power"] = db["users"][uid].get("base_power", 0) + 5
        return f"\n🌟 **THĂNG CẤP!** Đạt Level {db['users'][uid]['level']}! (+5 SM)"
    return ""

def get_total_power(db, uid):
    u = db["users"].get(uid, {})
    return u.get("base_power", 0) + (u.get("level", 1) * 2) + u.get("power", 0)

def check_and_pay_debt(db, uid):
    """Hệ thống tự động siết nợ khi người chơi có tiền"""
    u = db["users"][uid]
    msg = ""
    if u.get("debt", 0) > 0 and u.get("balance", 0) > 0:
        pay = min(u["balance"], u["debt"])
        u["balance"] -= pay
        u["debt"] -= pay
        msg = f"\n💸 **GIANG HỒ SIẾT NỢ:** Tự trừ **${pay}** trong ví! (Còn nợ: **${u['debt']}**)"
        if u["debt"] == 0: msg += " 🎉 Đã trả hết nợ!"
    return msg

def debt_reminder(db, uid):
    """Giang hồ đe dọa (Tỷ lệ xuất hiện 20%)"""
    u = db["users"].get(uid, {})
    if u.get("debt", 0) > 0 and random.random() < 0.20:
        return f"\n🔪 **TIN NHẮN ẨN DANH:** *\"Thằng kia, mày còn nợ tao ${u['debt']}, liệu hồn mà kiếm tiền trả sớm!\"*"
    return ""

# ====================================================================
# --- PHẦN 3: GIAO DIỆN (UI VIEWS) ---
# ====================================================================
class ShopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    async def buy_weapon(self, interaction, weapon_name):
        db, uid = load_db(), str(interaction.user.id)
        if uid not in db["users"]: return await interaction.response.send_message("❌ Chưa `/link`!", ephemeral=True)
        
        price, power = WEAPONS[weapon_name]["price"], WEAPONS[weapon_name]["power"]
        if db["users"][uid].get("balance", 0) < price: 
            return await interaction.response.send_message(f"❌ Không đủ ${price}!", ephemeral=True)
        if db["users"][uid].get("power", 0) >= power: 
            return await interaction.response.send_message("❌ Vũ khí hiện tại của bạn đã mạnh bằng hoặc hơn!", ephemeral=True)
        
        db["users"][uid]["balance"] -= price
        db["users"][uid]["weapon"] = weapon_name
        db["users"][uid]["power"] = power
        save_db(db)
        await interaction.response.send_message(f"✅ Bạn đã mua **{weapon_name}** {WEAPONS[weapon_name]['emoji']} thành công!", ephemeral=True)

    @discord.ui.button(label="Kiếm Gỗ ($50)", style=discord.ButtonStyle.secondary, emoji="🪵")
    async def btn_wood(self, i, b): await self.buy_weapon(i, "Kiếm Gỗ")
    @discord.ui.button(label="Kiếm Sắt ($150)", style=discord.ButtonStyle.secondary, emoji="🗡️")
    async def btn_iron(self, i, b): await self.buy_weapon(i, "Kiếm Sắt")
    @discord.ui.button(label="Kiếm Kim Cương ($500)", style=discord.ButtonStyle.primary, emoji="💎")
    async def btn_diamond(self, i, b): await self.buy_weapon(i, "Kiếm Kim Cương")
    @discord.ui.button(label="Thánh Kiếm ($1500)", style=discord.ButtonStyle.danger, emoji="⚔️", row=1)
    async def btn_excal(self, i, b): await self.buy_weapon(i, "Thánh Kiếm Excalibur")

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
                    debt_msg = check_and_pay_debt(db, uid) # Tự siết nợ
                    msg += f"<@{uid}>: Đặt **${tong_cuoc}** ➡️ Thắng **${tong_nhan}** 🎉{debt_msg}\n"
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
        if uid not in db["users"]: return await interaction.response.send_message("❌ Chưa `/link`!", ephemeral=True)
        if db["users"][uid].get("balance", 0) < amount: return await interaction.response.send_message(f"❌ Không đủ tiền trong ví!", ephemeral=True)
            
        db["users"][uid]["balance"] -= amount
        save_db(db)
        
        if uid not in self.baucua_view.bets: self.baucua_view.bets[uid] = []
        self.baucua_view.bets[uid].append({"animal": self.animal, "amount": amount})
        await interaction.response.send_message(f"✅ Bạn đã đặt cược **${amount}** vào **{self.animal.capitalize()}** {self.emoji}", ephemeral=True)

# ====================================================================
# --- PHẦN 4: SETUP BOT & LỆNH CHÍNH ---
# ====================================================================
class MyBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=discord.Intents.default())
    async def setup_hook(self): await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user.name} V11 ĐÃ SẴN SÀNG!')
    await process_pending_withdrawals(bot)
    if BACKUP_CHANNEL_ID and not auto_backup_task.is_running(): 
        auto_backup_task.start()
    await bot.change_presence(activity=discord.Game(name="/vaytien | /thuemhg"))

@tasks.loop(minutes=3)
async def auto_backup_task():
    global data_changed
    if data_changed and BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            async for msg in channel.history(limit=15):
                if msg.author == bot.user: await msg.delete()
            await channel.send(f"☁️ **BACKUP DỮ LIỆU V11** ({datetime.now().strftime('%H:%M')}):", file=discord.File(DB_FILE))
            data_changed = False
        except: pass

# --- QUẢN LÝ TÀI KHOẢN ---
@bot.tree.command(name="link", description="Tạo hồ sơ nhân vật (Liên kết tài khoản game).")
async def link(interaction: discord.Interaction, mc_name: str):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: 
        db["users"][uid] = {"balance": 0, "mc_name": mc_name, "weapon": "Tay không", "power": 0, "level": 1, "xp": 0, "debt": 0, "daily_hires": 0}
        save_db(db)
        await interaction.response.send_message(f"✅ Đã tạo hồ sơ nhân vật: **{mc_name}** thành công.")
    else: 
        await interaction.response.send_message("❌ Bạn đã có hồ sơ rồi!", ephemeral=True)

@bot.tree.command(name="vi", description="Xem thẻ nhân vật RPG.")
async def vi(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Bạn cần dùng lệnh `/link` trước!", ephemeral=True)
    u = db["users"][uid]
    
    embed = discord.Embed(title=f"📜 THẺ NHÂN VẬT: {interaction.user.display_name}", color=discord.Color.gold())
    embed.add_field(name="👤 Tên Game", value=f"`{u.get('mc_name', 'Unknown')}`", inline=False)
    embed.add_field(name="🔹 Cấp độ", value=f"**Lv {u.get('level', 1)}** (XP: {u.get('xp', 0)}/{u.get('level', 1)*100})", inline=True)
    embed.add_field(name="💳 Tiền mặt", value=f"**${u.get('balance', 0)}**", inline=True)
    embed.add_field(name="⚔️ Sức mạnh", value=f"**{get_total_power(db, uid)}**", inline=True)
    embed.add_field(name="🛡️ Vũ khí", value=f"{u.get('weapon', 'Tay không')} (+{u.get('power', 0)} SM)", inline=False)
    
    if u.get("debt", 0) > 0: 
        embed.add_field(name="⚠️ Khoản Nợ Xã Hội Đen", value=f"**${u['debt']}**", inline=True)
    if u.get("buff_mhg", False): 
        embed.add_field(name="🏕️ Mạo hiểm giả hộ tống", value="**Đang có (Dùng trong 1 trận)**", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Điểm danh nhận quà mỗi ngày.")
async def daily(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Bạn chưa `/link`!", ephemeral=True)
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    if db["users"][uid].get("last_daily", "") == current_date: 
        return await interaction.response.send_message("⏳ Bạn đã nhận quà hôm nay rồi, hãy quay lại vào ngày mai!", ephemeral=True)
    
    reward = random.randint(20, 50)
    db["users"][uid]["last_daily"] = current_date
    db["users"][uid]["balance"] = db["users"][uid].get("balance", 0) + reward
    
    debt_msg = check_and_pay_debt(db, uid)
    threat = debt_reminder(db, uid)
    save_db(db)
    
    await interaction.response.send_message(f"🎁 Bạn vừa điểm danh và nhận được **${reward}**.{debt_msg}{threat}")

# --- KINH TẾ & GIAO DỊCH ---
@bot.tree.command(name="pay", description="Chuyển tiền cho người khác.")
async def pay(interaction: discord.Interaction, nguoi_nhan: discord.Member, so_tien: int):
    db, uid, target_id = load_db(), str(interaction.user.id), str(nguoi_nhan.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Bạn chưa `/link`!", ephemeral=True)
    if target_id not in db["users"]: return await interaction.response.send_message("❌ Người nhận chưa `/link`!", ephemeral=True)
    if uid == target_id: return await interaction.response.send_message("❌ Không thể tự chuyển tiền cho chính mình!", ephemeral=True)
    if so_tien <= 0 or db["users"][uid].get("balance", 0) < so_tien: 
        return await interaction.response.send_message("❌ Số tiền không hợp lệ hoặc không đủ!", ephemeral=True)
        
    db["users"][uid]["balance"] -= so_tien
    db["users"][target_id]["balance"] += so_tien
    
    debt_msg = check_and_pay_debt(db, target_id)
    save_db(db)
    
    await interaction.response.send_message(f"💸 Bạn đã chuyển **${so_tien}** cho {nguoi_nhan.mention}.{debt_msg}")

@bot.tree.command(name="ruttien", description="Rút tiền Discord vào Game Minecraft.")
async def ruttien(interaction: discord.Interaction, so_tien: int):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"] or so_tien <= 0 or db["users"][uid]["balance"] < so_tien:
        return await interaction.response.send_message("❌ Không đủ tiền hoặc số tiền không hợp lệ!", ephemeral=True)
    
    await interaction.response.defer() 
    mc_name = db["users"][uid]["mc_name"]
    db["users"][uid]["balance"] -= so_tien
    db["pending"].append({"uid": uid, "amount": so_tien, "mc_name": mc_name})
    save_db(db)
    
    await interaction.followup.send(f"✅ Đã trừ **${so_tien}**.\n⏳ Lệnh chuyển tiền vào game của **{mc_name}** đang được xử lý.")
    await process_pending_withdrawals(bot)

@bot.tree.command(name="vaytien", description="Vay nặng lãi của Giang hồ (Tối đa $1000, Lãi 20%).")
async def vaytien(interaction: discord.Interaction, so_tien: int):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Chưa `/link`!", ephemeral=True)
    if so_tien <= 0: return await interaction.response.send_message("❌ Số tiền không hợp lệ!", ephemeral=True)
    
    current_debt = db["users"][uid].get("debt", 0)
    if current_debt + so_tien > 1000:
        return await interaction.response.send_message(f"❌ Giang hồ chỉ cho nợ tối đa $1000! (Bạn đang nợ: ${current_debt})", ephemeral=True)
        
    lai_suat = int(so_tien * 0.2) # Lãi cắt cổ 20%
    tong_no = so_tien + lai_suat
    
    db["users"][uid]["balance"] = db["users"][uid].get("balance", 0) + so_tien
    db["users"][uid]["debt"] = current_debt + tong_no
    save_db(db)
    
    await interaction.response.send_message(f"🚬 **GIANG HỒ:** *\"Cầm lấy **${so_tien}** mà tiêu! Ghi sổ nợ mày cộng thêm lãi 20% là **${tong_no}**. Có tiền tao tự trừ, trốn tao chặt chân!\"*")

@bot.tree.command(name="trano", description="Chủ động trả nợ cho Giang hồ.")
async def trano(interaction: discord.Interaction, so_tien: int):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Lỗi, chưa `/link`!", ephemeral=True)
    
    current_debt = db["users"][uid].get("debt", 0)
    if current_debt == 0: return await interaction.response.send_message("✅ Bạn đâu có nợ ai mà trả!", ephemeral=True)
    if so_tien <= 0 or db["users"][uid]["balance"] < so_tien: 
        return await interaction.response.send_message("❌ Tiền không hợp lệ hoặc ví của bạn không đủ!", ephemeral=True)
    
    pay_amount = min(so_tien, current_debt)
    db["users"][uid]["balance"] -= pay_amount
    db["users"][uid]["debt"] -= pay_amount
    save_db(db)
    
    msg = f"🤝 Bạn đã trả **${pay_amount}** cho giang hồ."
    if db["users"][uid]["debt"] == 0: msg += " 🎉 Chúc mừng bạn đã thoát cảnh nợ nần!"
    else: msg += f" (Còn nợ: **${db['users'][uid]['debt']}**)"
    
    await interaction.response.send_message(msg)

# --- TỔ ĐỘI (PARTY) ---
@bot.tree.command(name="lapdoi", description="Xin gia nhập tổ đội của một người chơi khác.")
async def lapdoi(interaction: discord.Interaction, doi_truong: discord.Member):
    uid, leader_id = str(interaction.user.id), str(doi_truong.id)
    if uid == leader_id:
        USER_PARTY[uid] = uid
        return await interaction.response.send_message("✅ Bạn đã tự tạo một tổ đội và làm Đội trưởng.")
        
    USER_PARTY[uid] = leader_id
    if leader_id not in USER_PARTY: USER_PARTY[leader_id] = leader_id # Tự động phong làm đội trưởng nếu chưa có đội
    await interaction.response.send_message(f"🤝 Bạn đã gia nhập tổ đội của **{doi_truong.display_name}**.")

@bot.tree.command(name="roidoi", description="Rời khỏi tổ đội hiện tại.")
async def roidoi(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if uid in USER_PARTY:
        del USER_PARTY[uid]
        await interaction.response.send_message("👋 Bạn đã rời khỏi tổ đội.")
    else: await interaction.response.send_message("❌ Bạn chưa tham gia tổ đội nào!", ephemeral=True)

@bot.tree.command(name="thongtindoi", description="Xem thông tin và Sức mạnh Tổ đội.")
async def thongtindoi(interaction: discord.Interaction):
    uid, db = str(interaction.user.id), load_db()
    if uid not in USER_PARTY: return await interaction.response.send_message("❌ Bạn không có trong tổ đội nào!", ephemeral=True)
    
    leader_id = USER_PARTY[uid]
    members = [m for m, l in USER_PARTY.items() if l == leader_id]
    
    desc = f"👑 **Đội trưởng:** <@{leader_id}>\n👥 **Thành viên:**\n"
    total_pow = 0
    for m in members:
        pw = get_total_power(db, m)
        total_pow += pw
        desc += f"- <@{m}> (SM: {pw})\n"
        
    desc += f"\n⚔️ **TỔNG SỨC MẠNH ĐỘI:** **{total_pow}**"
    await interaction.response.send_message(embed=discord.Embed(title="⛺ THÔNG TIN TỔ ĐỘI", description=desc, color=discord.Color.green()))

# --- SĂN QUÁI & VẬT PHẨM ---
@bot.tree.command(name="thuemhg", description="Thuê Mạo hiểm giả (Tăng 35% tỉ lệ thắng, $30/lần, Max 10 lần/ngày).")
async def thuemhg(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Chưa `/link`!", ephemeral=True)
    
    u = db["users"][uid]
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    if u.get("last_hire_date") != current_date:
        u["daily_hires"] = 0
        u["last_hire_date"] = current_date
        
    if u.get("daily_hires", 0) >= 10:
        return await interaction.response.send_message("🛑 Quán trọ đã hết Mạo hiểm giả! Ngày mai quay lại nhé (Đã thuê 10/10 lần).", ephemeral=True)
        
    if u.get("balance", 0) < 30: return await interaction.response.send_message("❌ Bạn cần $30 để thuê!", ephemeral=True)
    if u.get("buff_mhg", False): return await interaction.response.send_message("❌ Bạn đang có Mạo hiểm giả đi theo rồi, hãy đi đánh quái trước!", ephemeral=True)
        
    u["balance"] -= 30
    u["buff_mhg"] = True
    u["daily_hires"] = u.get("daily_hires", 0) + 1
    save_db(db)
    
    await interaction.response.send_message(f"🍻 Đã chi **$30** thuê Mạo hiểm giả! Trận đánh quái tiếp theo của bạn được **Cộng +35% Tỉ lệ thắng**. (Hôm nay đã thuê: {u['daily_hires']}/10)")

@bot.tree.command(name="santhu", description="Săn thú rừng kiếm XP & Tiền (Phí: $10).")
async def santhu(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"] or db["users"][uid].get("balance", 0) < 10: 
        return await interaction.response.send_message("❌ Cần $10 lệ phí để vào rừng!", ephemeral=True)
        
    db["users"][uid]["balance"] -= 10
    pw = get_total_power(db, uid)
    win_chance = min(90, 30 + pw)
    
    buff_msg = ""
    if db["users"][uid].get("buff_mhg", False):
        win_chance = min(95, win_chance + 35) 
        db["users"][uid]["buff_mhg"] = False 
        buff_msg = "\n🛡️ *Mạo hiểm giả đã xông lên đánh phụ bạn!*"
    
    if random.randint(1, 100) <= win_chance:
        r_cash, r_xp = random.randint(20, 50), random.randint(15, 30)
        db["users"][uid]["balance"] += r_cash
        
        debt_msg = check_and_pay_debt(db, uid)
        msg = f"🎉 Bạn hạ gục quái thú! Nhận **${r_cash}** & **{r_xp} XP**.{add_xp(db, uid, r_xp)}{buff_msg}{debt_msg}"
    else: 
        msg = f"💀 Quái vật quá mạnh, bạn phải tháo chạy và mất **$10**!{buff_msg}"
        
    msg += debt_reminder(db, uid) 
    save_db(db)
    await interaction.response.send_message(msg)

@bot.tree.command(name="sanboss", description="Cùng Tổ đội đánh Boss (Phí: $50/đội).")
async def sanboss(interaction: discord.Interaction):
    uid, db = str(interaction.user.id), load_db()
    if uid not in USER_PARTY or USER_PARTY[uid] != uid: 
        return await interaction.response.send_message("❌ Chỉ Đội trưởng mới được phát động Săn Boss!", ephemeral=True)
    if db["users"].get(uid, {}).get("balance", 0) < 50: 
        return await interaction.response.send_message("❌ Đội trưởng cần $50 phí khiêu chiến!", ephemeral=True)
        
    await interaction.response.defer() 
    
    members = [u for u, p in USER_PARTY.items() if p == uid]
    total_power = sum(get_total_power(db, m) for m in members)
    db["users"][uid]["balance"] -= 50
    
    boss = random.choice(BOSSES)
    win_chance = min(95, 10 + int(total_power * 0.5))
    
    buff_msg = ""
    if db["users"][uid].get("buff_mhg", False):
        win_chance = min(95, win_chance + 35)
        db["users"][uid]["buff_mhg"] = False
        buff_msg = "\n🏕️ *Mạo hiểm giả của Đội trưởng đã buff (+35% Tỉ lệ thắng) cho toàn đội!*\n"
    
    if random.randint(1, 100) <= win_chance:
        cash, xp = random.randint(100, 200), random.randint(30, 80)
        msg = f"🎉 **CHIẾN THẮNG!** Đội bạn đã hạ gục **{boss['name']}**!{buff_msg}\n💰 Mỗi người nhận được: **${cash}** & **{xp} XP**\n"
        
        for m in members:
            db["users"][m]["balance"] += cash
            debt_msg = check_and_pay_debt(db, m)
            msg += add_xp(db, m, xp) + debt_msg
            if random.random() < 0.40: # 40% rớt đồ
                if "inventory" not in db["users"][m]: db["users"][m]["inventory"] = {}
                db["users"][m]["inventory"][boss["drop"]] = db["users"][m]["inventory"].get(boss["drop"], 0) + 1
                msg += f"\n🎁 <@{m}> nhặt được 1x **{boss['drop']}**!"
    else: 
        msg = f"💀 **THẤT BẠI!** **{boss['name']}** quá trâu, cả đội phải rút lui. Đội trưởng mất $50.{buff_msg}"
        
    save_db(db)
    await interaction.followup.send(msg)

@bot.tree.command(name="ruongdo", description="Xem túi đồ của bạn.")
async def ruongdo(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Bạn chưa `/link`!", ephemeral=True)
    
    inv = db["users"][uid].get("inventory", {})
    if not inv: return await interaction.response.send_message("🎒 Rương đồ của bạn trống rỗng.", ephemeral=True)
        
    msg = "🎒 **RƯƠNG ĐỒ CỦA BẠN:**\n"
    for item, qty in inv.items(): msg += f"- **{item}**: {qty} cái\n"
    await interaction.response.send_message(msg)

@bot.tree.command(name="banvatpham", description="Bán vật phẩm săn Boss kiếm tiền.")
async def banvatpham(interaction: discord.Interaction, ten_vat_pham: str, so_luong: int):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"] or so_luong <= 0: return await interaction.response.send_message("❌ Dữ liệu không hợp lệ!", ephemeral=True)
    
    inventory = db["users"][uid].get("inventory", {})
    if inventory.get(ten_vat_pham, 0) < so_luong: 
        return await interaction.response.send_message(f"❌ Bạn không có đủ {so_luong}x {ten_vat_pham}!", ephemeral=True)
        
    item_price = 50
    for b in BOSSES:
        if b["drop"] == ten_vat_pham: item_price = b["drop_price"]

    earned = item_price * so_luong
    db["users"][uid]["inventory"][ten_vat_pham] -= so_luong
    if db["users"][uid]["inventory"][ten_vat_pham] == 0: 
        del db["users"][uid]["inventory"][ten_vat_pham]
    
    db["users"][uid]["balance"] += earned
    
    debt_msg = check_and_pay_debt(db, uid)
    save_db(db)
    
    await interaction.response.send_message(f"💸 Đã bán **{so_luong}x {ten_vat_pham}** và thu về **${earned}**!{debt_msg}")

# --- MINI GAMES & CỬA HÀNG ---
@bot.tree.command(name="shop", description="Mở cửa hàng vũ khí.")
async def shop(interaction: discord.Interaction): 
    await interaction.response.send_message(embed=discord.Embed(title="🛒 SHOP VŨ KHÍ", description="Mua vũ khí để tăng sức mạnh đánh quái!", color=discord.Color.purple()), view=ShopView())

@bot.tree.command(name="baucua", description="Tạo sòng Bầu Cua Tôm Cá.")
async def baucua(interaction: discord.Interaction): 
    await interaction.response.send_message(embed=discord.Embed(title="🎪 SÒNG BẦU CUA", description=f"Nhà cái: **{interaction.user.display_name}**\nBấm nút bên dưới để cược!", color=discord.Color.blue()), view=BauCuaView(host_id=interaction.user.id))

# CHẠY BOT
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
