import discord
from discord.ext import commands
import json
import random
import time
import os
from flask import Flask
from threading import Thread

# ================= TẠO WEB SERVER ĐỂ GIỮ BOT LUÔN CHẠY =================
app = Flask('')

@app.route('/')
def home():
    return "Bot đang chạy online!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# ====================================================================

# Đọc cấu hình bảo mật từ hệ thống (sẽ cài đặt trên Render)
TOKEN = os.environ.get('DISCORD_TOKEN')
CONSOLE_CHANNEL_ID = int(os.environ.get('CONSOLE_CHANNEL_ID', 0))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

DB_FILE = 'users.json'

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

@bot.event
async def on_ready():
    print('=========================================')
    print(f'✅ Bot {bot.user} đã sẵn sàng hoạt động 24/7!')
    print('=========================================')

# LỆNH 1: LIÊN KẾT TÀI KHOẢN (!link)
@bot.command()
async def link(ctx, mc_name: str):
    db = load_db()
    db[str(ctx.author.id)] = {"mc_name": mc_name, "last_daily": 0}
    save_db(db)
    await ctx.send(f'✅ Đã liên kết tài khoản Discord với nhân vật game: **{mc_name}**')

# LỆNH 2: ĐIỂM DANH HÀNG NGÀY (Nhận ngẫu nhiên từ 5 đến 30)
@bot.command()
async def daily(ctx):
    db = load_db()
    user_id = str(ctx.author.id)
    
    if user_id not in db:
        await ctx.send("❌ Bạn chưa liên kết tài khoản! Gõ `!link <tên_trong_game>` nhé.")
        return

    current_time = time.time()
    last_daily = db[user_id].get("last_daily", 0)
    
    if current_time - last_daily < 86400: 
        await ctx.send("⏳ Bạn đã nhận quà rồi! Hãy quay lại vào ngày mai.")
        return
        
    db[user_id]["last_daily"] = current_time
    save_db(db)
    
    mc_name = db[user_id]["mc_name"]
    
    # ĐỔI TẠI ĐÂY: Nhận ngẫu nhiên từ 5 đến 30
    reward = random.randint(5, 30) 
    
    console_channel = bot.get_channel(CONSOLE_CHANNEL_ID)
    if console_channel:
        await console_channel.send(f'eco give {mc_name} {reward}')
        await ctx.send(f'🎁 Điểm danh thành công! Đã bơm **${reward}** vào túi **{mc_name}** trong game.')
    else:
        await ctx.send("❌ Lỗi cấu hình: Chưa cài đặt đúng ID kênh Console.")

# LỆNH 3: BẦU CUA TÔM CÁ (!baucua)
@bot.command()
async def baucua(ctx, choice: str, bet: int):
    db = load_db()
    user_id = str(ctx.author.id)
    
    if user_id not in db:
        await ctx.send("❌ Bạn chưa liên kết tài khoản! Gõ `!link <tên_trong_game>` trước.")
        return
        
    if bet <= 0:
        await ctx.send("❌ Số tiền cược phải lớn hơn 0!")
        return

    linh_vat = ['bầu', 'cua', 'tôm', 'cá', 'gà', 'nai']
    choice = choice.lower()
    
    if choice not in linh_vat:
        await ctx.send(f"❌ Vui lòng chọn 1 trong các con: {', '.join(linh_vat)}")
        return
        
    ket_qua = [random.choice(linh_vat) for _ in range(3)]
    so_lan_trung = ket_qua.count(choice)
    
    mc_name = db[user_id]["mc_name"]
    console_channel = bot.get_channel(CONSOLE_CHANNEL_ID)
    
    ket_qua_str = " - ".join([x.capitalize() for x in ket_qua])
    await ctx.send(f'🎲 Kết quả lắc: **[ {ket_qua_str} ]**')
    
    if so_lan_trung > 0:
        tien_thang = bet * so_lan_trung
        await console_channel.send(f'eco give {mc_name} {tien_thang}')
        await ctx.send(f'🎉 Trúng {so_lan_trung} con **{choice.capitalize()}**. Cộng **${tien_thang}** vào game!')
    else:
        await console_channel.send(f'eco take {mc_name} {bet}')
        await ctx.send(f'😢 Không có con **{choice.capitalize()}**. Bạn bị trừ **${bet}** trong game!')

# Chạy web server ẩn trước, sau đó chạy bot
keep_alive()
bot.run(TOKEN)
