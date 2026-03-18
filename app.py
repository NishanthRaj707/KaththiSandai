from flask import Flask,render_template,request,redirect,url_for,session,jsonify
from google.oauth2 import id_token
from google.auth.transport import requests
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash,generate_password_hash
from functools import wraps
from main import create_ai
import os,hashlib,hmac,csv,datetime,dateutil

load_dotenv()

mark_allotment = {
    'easy':   [4,2],
    'medium': [8,3],
    'hard':   [12,4]
}

def next_month_date():
    present_date=datetime.datetime.now()
    next_month_date = present_date + dateutil.relativedelta.relativedelta(months=+1)
    return next_month_date.strftime("%A, %B %d, %Y, %I:%M %p")

def load_basic_details(user):
    session["userid"]=user.id
    session["userid"]=user.id
    session["username"]=user.username
    session["grade"]=user.grade
    session["physicsglory"]=user.physics_glory
    session["chemistryglory"]=user.chemistry_glory
    session["mathsglory"]=user.maths_glory
    session["pakkodaglory"]=user.pakkoda_glory
    session["is_pro"]=user.is_pro
    session["pro_expiry"]=user.pro_expiry

def check_pro_expiry(user):
    current_date=datetime.datetime.now()
    expiry_date=datetime.datetime.strptime(session["pro_expiry"],"%Y-%m-%d %H:%M:%S")
    if current_date>=expiry_date:
        user.is_pro=0
        user.pro_expiry=None
        db.session.commit()
        session["is_pro"]=0
        session["pro_expiry"]=None
        return True

GOOGLE_CLIENT_ID=os.getenv("GOOGLE_CLIENT_ID")
WEBHOOK_SECRET=os.getenv("WEBHOOK_SECRET")
app=Flask(__name__)
app.secret_key=os.getenv("SECRET_KEY")

def login_required(function):
    @wraps(function) # ⚔️ Crucial: Keeps the function name and metadata intact
    def wrapper(*args, **kwargs): # ⚔️ Allows passing URL variables if needed
        if "userid" not in session:
            # Better to use url_for than a hardcoded string "/"
            if "email" not in session:
                return redirect("/") 
        
        # ⚔️ THE FIX: You must CALL the function and return its result
        return function(*args, **kwargs)
    return wrapper

@app.route('/dashboard')
@login_required
def dashboard():
    session["rank"]=rank_classification()
    return render_template("dashboard.html")

@app.route('/')
def index():
    return render_template("main.html")

@app.route('/auth/google-callback',methods=['POST'])
def google_login():
    
    data = request.form.get("credential")
    
    try:
        
        id_info = id_token.verify_oauth2_token(data,requests.Request(), GOOGLE_CLIENT_ID)
        gmail_email = id_info['email'] # Verified email
        
        session["email"]=gmail_email
        user = User.query.filter_by(email=gmail_email).first()
        
        if user:
            load_basic_details(user)
            if session.get("is_pro"): check_pro_expiry(user) 
            # Success! Redirect with the actual Integer ID
            return redirect(url_for('dashboard'))
      
        # New Warrior detected - send to Enrollment
        return redirect("/enrollment")

    except Exception as e:
        # Invalid Token
        return f"Unauthorized: Token verification failed{e}",401


@app.route('/razorpay-webhook', methods=['POST'])
def razorpay_webhook():
    webhook_secret = WEBHOOK_SECRET # You set this in Razorpay Dashboard
    data = request.data
    signature = request.headers.get('X-Razorpay-Signature')

    # ⚔️ Security Check: Verify that this message actually came from Razorpay
    expected_signature = hmac.new(webhook_secret.encode(), data, hashlib.sha256).hexdigest()

    if signature == expected_signature:
        event_data = request.json
        if event_data['event'] == 'payment.captured':
            email = event_data['payload']['payment']['entity']['email']
            amount= event_data['payload']['payment']['entity']['amount']
            # Find the warrior and upgrade them
            user = User.query.filter_by(email=email).first()
            if user:
                user.is_pro = 1
                user.pro_expiry=next_month_date()
                session["is_pro"]=1
                session["pro_expiry"]=next_month_date()
                db.session.commit()
                with open("pro_payment_logs.csv",'a',newline='') as f:
                    writer=csv.writer(f)
                    initial_date=datetime.datetime.now()
                    f.writerow([initial_date,next_month_date(),user.id,email,amount])
                
        return redirect(url_for("payment_success"))
    else:
        return "Invalid Signature", 400
    
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=="POST":
        username=request.form.get('username')
        password=request.form.get('password')
        user=User.query.filter_by(username=username).first()
        if user:
            if user.check_password(password):
                load_basic_details(user)
                if session.get("is_pro"): check_pro_expiry(user) 
                return redirect(url_for("dashboard"))
            else:
                return render_template("login.html",invalidpass=1,invaliduser=0)
        else:
            return render_template("login.html",invaliduser=1,invalidpass=0)
    return render_template("login.html",invaliduser=0,invalidpass=0)

@app.route("/enrollment",methods=["GET",'POST'])
@login_required
def enrollment():
    if request.method=="POST":
        user_name=request.form.get('username')
        password=request.form.get('password')
        email=session.get("email")
        grade=request.form.get('grade')
        
        if User.query.filter_by(username=user_name).all():
            return render_template("enrollment.html",existsuser=1)
        else:
            new_user=User(username=user_name,email=email,grade=grade)
            new_user.save_password(password)
            db.session.add(new_user)
            db.session.commit()
            session["userid"]=new_user.id
            session["username"]=new_user.username
            session["grade"]=new_user.grade
            session["physicsglory"]=new_user.physics_glory
            session["chemistryglory"]=new_user.chemistry_glory
            session["mathsglory"]=new_user.maths_glory
            session["pakkodaglory"]=new_user.pakkoda_glory
            print("pakkodagloary",session.get("pakkodaglory"))

            return redirect("/dashboard")
    
    return render_template("enrollment.html")

@app.route('/profile',methods=["POST","GET"])
@login_required
def profile():
    initial=session.get("username")[0]
    return render_template("profile.html",initialletter=initial)

@app.route('/leaderboard',methods=["GET","POST"])
@login_required
def leaderboard():
    glory=User.pakkoda_glory
    if request.method=="POST":
        glory=request.form.get("subject-filter")
        if glory=="physics_glory":
            glory=User.physics_glory
        elif glory=="chemistry_glory":
            glory=User.chemistry_glory
        elif glory=="maths_glory":
            glory=User.physics_glory
    listofusers=User.query.order_by(glory.desc()).all() 
    first=listofusers[0]
    second=listofusers[1] if len(listofusers)>=2 else 0
    third=listofusers[2] if len(listofusers)>=3 else 0
    others=listofusers[3:] if len(listofusers)>3 else 0
    mylist=[(i+1,listofusers[i]) for i in range(len(listofusers)) if listofusers[i].id == session.get("userid")]
    myrank,my=mylist[0]
    return render_template("leaderboard.html",first=first,second=second,third=third,others=others,my=my,myrank=myrank)

@app.route("/generate-battle-api",methods=["POST"])
def generate_battle_api():
    data=request.get_json()
    subject=data.get("subject")
    grade=data.get("grade")
    exam_type=data.get("exam_type")
    difficulty=data.get("difficulty")
    topic=data.get("topic")

    questions=create_ai(subject=subject,grade=grade,exam_type=exam_type,difficulty=difficulty,topic=topic)

    if questions:
            # Save questions in session so the next page can see them
            session['current_questions'] = questions
            return jsonify({"status": "success", "redirect": url_for('test_template')})
        
    return jsonify({"status": "error", "message": "The spirits failed to conjure questions."}), 500

@app.route("/test_template",methods=["GET","POST"])
@login_required
def test_template():
    print(session.get("current_questions"))
    return render_template("test_template.html",current_questions=session.get("current_questions"))

@app.route("/loading",methods=["GET"])
@login_required
def loading():
    return render_template("loading.html")

@app.route("/specific_test",methods=["GET","POST"])
@login_required
def specific_test():
    if request.method=="POST":
        session["test_subject"]=request.form.get("subject")
        session["test_exam_type"]=request.form.get("exam_type")
        session["test_difficulty"]=request.form.get("Difficulty")
        session["test_topic"]=request.form.get("get")
        return redirect(url_for("loading"))
    return render_template("specific_test.html")

@app.route("/submit-battle",methods=["GET","POST"])
def submit_test():
    data=request.get_json()
    correct_answer=data.get("canswers")
    print("correct answers",correct_answer)
    user_answer=data.get("answers")
    print("Answers",user_answer)
    subject=session.get("test_subject")
    print("subject",subject)
    difficulty=session.get("test_difficulty").lower()
    mark=no_of_correct=no_of_wrong=0
    for i in correct_answer:
        x=correct_answer[i].lower()
        y=user_answer[i].lower()
        if x==y:
            mark+=mark_allotment[difficulty][0]
            no_of_correct+=1
        else:
            mark-=mark_allotment[difficulty][-1]
            no_of_wrong+=1
    subjectglory=subject.lower()+'glory'
    session["nocorrect"]=no_of_correct
    session["nowrong"]=no_of_wrong
    session["test_result"]=mark
    if subject.lower() not in ["cs","biology"]:
        session["pakkodaglory"]=int(session.get("pakkodaglory"))+round((mark/3),1)
        session[subjectglory]=int(session.get(subjectglory))+mark
        user=User.query.get_or_404(int(session.get("userid")))
        user.pakkoda_glory=session.get("pakkodaglory")
        subject_map={
            'physics':user.physics_glory,
            'chemistry':user.chemistry_glory,
            'maths':user.maths_glory
        }
        subject_map[subject]=subject_map[subject]+mark
        db.session.commit()

    return {'status':'success'}

@app.route('/billing',methods=["POST","GET"])
def biling():
    return render_template("billing.html")

@app.route('/payment_success')
def payment_success():
    return render_template("payment_success.html")

@app.route("/result")
def result():
    return render_template("result.html")




app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user_authentication.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db=SQLAlchemy()
db.init_app(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password =db.Column(db.String(256),nullable=False)
    grade=db.Column(db.Integer,nullable=False)
    physics_glory = db.Column(db.Integer, default=500)
    chemistry_glory = db.Column(db.Integer, default=500)
    maths_glory = db.Column(db.Integer, default=500)
    pakkoda_glory = db.Column(db.Integer, default=500)
    rank=db.Column(db.String(50),default="Recruit 🛡️")
    is_pro=db.Column(db.Integer,default=0)
    pro_expiry=db.Column(db.DateTime)

    
    def save_password(self,password):
        self.password=generate_password_hash(password)
    
    def check_password(self,password):
        return check_password_hash(self.password,password)


def rank_classification():
    glory=session.get("pakkodaglory")
    if glory < 650:  return "Recruit 🛡️"
    elif glory < 800:  return "Soldier ⚔️"
    elif glory < 950:  return "Guardian 🏰"
    elif glory < 1100: return "Commander 🦅"
    elif glory < 1400: return "Champion 💎"
    elif glory < 2000: return "Vanguard 🔥"
    return "Warlord 👑"
    
    
if __name__=="__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

