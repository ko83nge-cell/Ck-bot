CK BOT — Render Free Web Service တပ်ဆင်နည်း

ပါဝင်သောဖိုင်များ
- main.py: CK BOT အဓိကကုဒ် (လက်ရှိ Bot စနစ်များကို ထိန်းသိမ်းထားသည်)
- requirements.txt: Python လိုအပ်သော package များ
- Procfile: Render Web Service start command
- render.yaml: Render Free Web Service နှင့် /healthz Health Check သတ်မှတ်ချက်
- .github/workflows/render-keepalive.yml: GitHub Actions မှ ၁၀ မိနစ်တစ်ကြိမ် Health URL ကို ping လုပ်ရန် (ရွေးချယ်နိုင်သည်)

Render မှာ Deploy လုပ်ရန်
1. GitHub repository Ck-bot ကိုဖွင့်ပါ။
2. အဟောင်း main.py, requirements.txt, Procfile ကို ဒီဖိုင်အသစ်များဖြင့် အစားထိုးပါ။
3. render.yaml ကို repository root မှာထားပါ။ .github/workflows/render-keepalive.yml ကိုလည်း folder လမ်းကြောင်းအတိုင်းတင်ပါ။
4. Render Dashboard > New > Web Service မှ GitHub repository ကိုချိတ်ပါ။
5. Runtime Python၊ Build Command `pip install --no-cache-dir -r requirements.txt`၊ Start Command `python main.py` ကိုသတ်မှတ်ပါ။
6. Instance Type ကို Free ရွေးပါ။ Health Check Path ကို `/healthz` ထားပါ။
7. Environment Variables ထဲတွင် TELEGRAM_TOKEN နှင့် BOT_OWNER_ID ထည့်ပါ။ AI သုံးမည်ဆိုလျှင် OPENAI_API_KEY ကိုလည်းထည့်ပါ။
8. Deploy ပြီး Logs ထဲတွင် `Render HTTP health server listening` နှင့် `CK BOT started` စာသားများကိုစစ်ပါ။
9. Browser မှ `https://သင့်-service-အမည်.onrender.com/healthz` ကိုဖွင့်ပြီး `CK BOT is running` ပြန်လာမလာ စစ်ပါ။

အရေးကြီးသော Render Free ကန့်သတ်ချက်များ
- Render Free Web Service သည် ၁၅ မိနစ်အတွင်း inbound traffic မရပါက sleep ဝင်နိုင်သည်။ ပြန်နိုးရန် နောက် request တစ်ခုလာသောအခါ စတင်ချိန်ယူနိုင်သည်။
- အခမဲ့ Web Service တွင် Persistent Disk မရပါ။ SQLite ဖိုင်အပါအဝင် local files များသည် restart, redeploy သို့မဟုတ် sleep/spin-down အပြီး မတည်မြဲနိုင်ပါ။ Database ကို ရေရှည်မပျောက်စေလိုလျှင် persistent database လိုအပ်သည်။
- GitHub Actions workflow သည် ၁၀ မိနစ်တစ်ကြိမ် ping ပို့ရန် ကြိုးစားပေးသည်။ GitHub schedule သည် အချိန်တိတိကျကျ run မည်ဟု အာမမခံနိုင်သောကြောင့် ၂၄/၇ အမြဲနိုးနေမည်ဟု အာမမခံနိုင်ပါ။ Workflow အလုပ်လုပ်ရန် GitHub repository Settings > Secrets and variables > Actions > New repository secret မှာ `RENDER_URL` အမည်ဖြင့် `https://သင့်-service-အမည်.onrender.com` ကိုထည့်ပါ။
- Bot Token နှင့် API Key များကို GitHub code ထဲ မရေးပါနှင့်။ Render Environment Variables ထဲတွင်သာထားပါ။
- Railway အတွက် သတ်မှတ်ခဲ့သော `DB_PATH=/data/ck_bot.db` ကို Render Free မှာ မသုံးပါနှင့်။ မသတ်မှတ်ထားလျှင် main.py က `ck_bot.db` ကို အသုံးပြုမည်။ Free filesystem သည် ယာယီသာဖြစ်သည်။

Deploy စစ်ဆေးရန်
- Telegram မှ Bot ကို /start ပို့ပါ။
- /ping နှင့် /botstatus စမ်းပါ။
- TikTok public link တစ်ခုဖြင့် Video/Photo စနစ်ကို သီးခြားစမ်းပါ။
- Deploy အောင်မြင်ခြင်းတစ်ခုတည်းဖြင့် TikTok extractor နှင့် AI API အားလုံး အောင်မြင်ကြောင်း မဆိုလိုပါ။ Logs ကိုစစ်ဆေးပါ။
