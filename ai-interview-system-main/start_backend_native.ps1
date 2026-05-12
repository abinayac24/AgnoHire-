cd d:\Interview_System\AI_Interview_System
C:\Users\user\AppData\Local\Programs\Python\Python310\python.exe -m venv venv310_win
.\venv310_win\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 9000
