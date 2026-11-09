CK BOT — README (မြန်မာဘာသာ)

၁။ Project ထဲတွင် ပါဝင်သောဖိုင်များ

-   main.py : Telegram Bot ၏ အဓိက Python code
-   requirements.txt : လိုအပ်သော Python package များ
-   Procfile : Railway က Bot ကို စတင်ရန် အသုံးပြုသော command
-   README_MM.txt : တပ်ဆင်အသုံးပြုနည်း လမ်းညွှန် (ဤဖိုင်)

၂။ GitHub သို့ တင်ရန်

ဖိုင် ၄ ခုလုံးကို Ck-bot Repository ၏ ပင်မနေရာ (root) တွင် တင်ပါ။ ဖိုင်အမည်များကို
အောက်ပါအတိုင်း အတိအကျထားပါ။

main.py requirements.txt Procfile README_MM.txt

၃။ Railway တွင် Deploy လုပ်ရန်

1.  Railway တွင် Project အသစ်ဖွင့်ပါ။
2.  Deploy from GitHub Repo ကိုရွေးပြီး Ck-bot Repository ကို ချိတ်ပါ။
3.  Variables ထဲတွင် အောက်ပါ Environment Variables များ ထည့်ပါ။

TELEGRAM_TOKEN = သင့် Telegram Bot Token BOT_OWNER_ID = Bot ပိုင်ရှင်၏ Telegram
User ID DB_PATH = /data/ck_bot.db

AI စနစ်အသုံးပြုရန်: OPENAI_API_KEY = သင့် OpenAI API Key

သတိပြုရန်: - Token နှင့် API Key များကို GitHub code ထဲတွင် မရေးပါနှင့်။ - အဆိုပါ
လျှို့ဝှက်တန်ဖိုးများကို Railway Variables ထဲတွင်သာ ထည့်ပါ။ - BOT_OWNER_ID ကို မသတ်မှတ်ထားလျှင်
Owner-only လုပ်ဆောင်ချက်အချို့ မရနိုင်ပါ။ - AI API Key မထည့်ထားလျှင် AI လုပ်ဆောင်ချက်များ
မရနိုင်ပါ။

၄။ Database အချက်အလက် မပျောက်စေရန်

Railway တွင် Volume တစ်ခုဖန်တီးပြီး /data တွင် Mount လုပ်ပါ။ DB_PATH ကို
/data/ck_bot.db ဟု သတ်မှတ်ပါ။ Volume မတပ်ထားလျှင် Redeploy သို့မဟုတ် Instance
ပြောင်းချိန်တွင် Local SQLite database အချက်အလက်များ မတည်မြဲနိုင်ပါ။

၅။ Telegram Bot အသုံးပြုရန်

-   Bot ကို Telegram တွင်ဖွင့်ပြီး /start ပို့ပါ။
-   အကူအညီအတွက် /help ကို အသုံးပြုပါ။
-   AI အတွက် /aimenu သို့မဟုတ် /ai ကို အသုံးပြုပါ။
-   Bot အခြေအနေစစ်ရန် /ping နှင့် /botstatus ကို အသုံးပြုပါ။
-   Owner သည် Private Chat မှ /healthcheck ဖြင့် Database နှင့် Telegram API
    ချိတ်ဆက်မှုကို စစ်ဆေးနိုင်ပါသည်။

၆။ Group နှင့် Channel အသုံးပြုမှု

Group စနစ်အချို့အတွက် Bot ကို သက်ဆိုင်ရာ Group တွင် Admin ခန့်ထားရန် လိုအပ်သည်။ Channel
စနစ်များအတွက် Bot ကို Channel Admin ခန့်ထားပြီး လိုအပ်သော ခွင့်ပြုချက်များ ပေးထားပါ။
Group စနစ်များကို /groupmenu၊ Channel စနစ်များကို /channelmenu ဖြင့် ကြည့်နိုင်သည်။
Setting လမ်းညွှန်အတွက် /sethelp ကို အသုံးပြုပါ။

၇။ လိုအပ်သော Package များ

requirements.txt တွင် လက်ရှိ သတ်မှတ်ထားသည်များ: - python-telegram-bot - yt-dlp -
gallery-dl

Railway က Deploy လုပ်ချိန်တွင် requirements.txt အတိုင်း Package များကို
တပ်ဆင်ပေးမည်ဖြစ်သည်။

၈။ အရေးကြီးသော မှတ်ချက်

README_MM.txt သည် လမ်းညွှန်ဖိုင်သာဖြစ်ပြီး Bot စတင်အလုပ်လုပ်ရန် မဖြစ်မနေလိုအပ်သော Runtime ဖိုင်
မဟုတ်ပါ။ အဓိကလိုအပ်သောဖိုင်များမှာ main.py, requirements.txt နှင့် Procfile ဖြစ်သည်။

Bot အလုပ်လုပ်မှုသည် Telegram Token မှန်ကန်မှု၊ Railway Variables၊ Deploy Logs၊ Bot
ခွင့်ပြုချက်များနှင့် ပြင်ပ API များ၏ ရရှိနိုင်မှုအပေါ် မူတည်ပါသည်။ Deploy
အောင်မြင်ခြင်းတစ်ခုတည်းဖြင့် Feature အားလုံး အပြည့်အဝ စမ်းသပ်ပြီးကြောင်း မဆိုလိုပါ။
