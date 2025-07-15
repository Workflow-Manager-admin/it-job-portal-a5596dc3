from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from jose import JWTError, jwt

# Secret for JWT. In production load from env.
JWT_SECRET = "SECRET_FOR_DEV"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# In-memory 'databases'
users: Dict[str, Dict[str, Any]] = {}         # key: email
jobs: Dict[int, Dict[str, Any]] = {}          # key: job id
applications: Dict[int, Dict[str, Any]] = {}  # key: application id

# Helpers for auto-increment IDs
last_job_id = 0
last_app_id = 0

# === MODELS ===
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str
    role: str

class UserRegisterBase(BaseModel):
    email: EmailStr = Field(..., description="User email (must be unique)")
    password: str = Field(..., min_length=6, description="Password (min 6 chars)")
    name: str = Field(..., description="Full name")

class JobSeekerRegister(UserRegisterBase):
    resume: Optional[str] = Field(None, description="Resume/CV text or link")
    role: str = Field("jobseeker", const=True)

class EmployerRegister(UserRegisterBase):
    company_name: str = Field(..., description="Employer company name")
    role: str = Field("employer", const=True)

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    role: str = Field(..., description="jobseeker or employer")

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: str

class JobBase(BaseModel):
    title: str
    description: str
    company: str
    location: str
    skills: List[str]
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None

class Job(JobBase):
    id: int
    posted_by: str
    created_at: datetime

class JobCreate(JobBase):
    pass

class ApplicationBase(BaseModel):
    job_id: int
    seeker_email: EmailStr
    cover_letter: Optional[str] = None

class Application(ApplicationBase):
    id: int
    status: str  # pending, reviewed, rejected, accepted
    applied_at: datetime

class ApplicationReview(BaseModel):
    status: str = Field(..., regex="^(reviewed|rejected|accepted)$")

class JobFilter(BaseModel):
    query: Optional[str] = Field(None, description="Job title or description search")
    location: Optional[str] = None
    skills: Optional[List[str]] = None

# === AUTH/JWT ===
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# PUBLIC_INTERFACE
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Generate JWT token for given data dict"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

# PUBLIC_INTERFACE
def authenticate_user(email: str, password: str, role: str):
    """Authenticate user by email, password, and role."""
    user = users.get(email)
    if not user or user["password"] != password or user["role"] != role:
        return None
    return user

# PUBLIC_INTERFACE
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get the current logged-in user using JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        email: str = payload.get("email")
        role: str = payload.get("role")
        if email is None or role not in ["jobseeker", "employer"]:
            raise credentials_exception
        user = users.get(email)
        if not user or user["role"] != role:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception

# === FASTAPI APP SETUP ===
app = FastAPI(
    title="IT Job Portal Backend API",
    description="Backend API for IT Job Portal. Supports job seeker & employer flows.",
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "Authentication (registration, login)"},
        {"name": "jobs", "description": "Job CRUD & search"},
        {"name": "applications", "description": "Job applications (apply/review)"},
        {"name": "dashboard", "description": "User dashboards"}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# === ROUTER: AUTH ===
auth_router = APIRouter(prefix="/auth", tags=["auth"])

# PUBLIC_INTERFACE
@auth_router.post("/register/jobseeker", response_model=UserBase, summary="Register new job seeker")
def register_job_seeker(data: JobSeekerRegister = Body(...)):
    if data.email in users:
        raise HTTPException(status_code=400, detail="Email already registered")
    users[data.email] = data.dict()
    return UserBase(email=data.email, name=data.name, role="jobseeker")

# PUBLIC_INTERFACE
@auth_router.post("/register/employer", response_model=UserBase, summary="Register new employer")
def register_employer(data: EmployerRegister = Body(...)):
    if data.email in users:
        raise HTTPException(status_code=400, detail="Email already registered")
    users[data.email] = data.dict()
    return UserBase(email=data.email, name=data.name, role="employer")

# PUBLIC_INTERFACE
@auth_router.post("/token", response_model=Token, summary="Get access token (login)")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password, form_data.scopes[0] if form_data.scopes else "jobseeker")
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email, password, or role")
    access_token = create_access_token(data={"email": user["email"], "role": user["role"]})
    return {"access_token": access_token, "token_type": "bearer"}

# PUBLIC_INTERFACE
@auth_router.post("/login", response_model=Token, summary="Login and get access token")
def login_alt(data: UserLogin):
    user = authenticate_user(data.email, data.password, data.role)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email, password, or role")
    access_token = create_access_token(data={"email": user["email"], "role": user["role"]})
    return {"access_token": access_token, "token_type": "bearer"}

# === ROUTER: JOBS ===
jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])

# PUBLIC_INTERFACE
@jobs_router.post("/", response_model=Job, status_code=201, summary="Post a new job")
def post_job(job: JobCreate, current_user: dict = Depends(get_current_user)):
    global last_job_id
    if current_user["role"] != "employer":
        raise HTTPException(status_code=403, detail="Only employers can post jobs")
    last_job_id += 1
    new_job = Job(
        id=last_job_id,
        title=job.title,
        description=job.description,
        company=current_user.get("company_name", job.company),
        location=job.location,
        skills=job.skills,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        posted_by=current_user["email"],
        created_at=datetime.utcnow(),
    )
    jobs[last_job_id] = new_job.dict()
    return new_job

# PUBLIC_INTERFACE
@jobs_router.get("/", response_model=List[Job], summary="List jobs (with optional filters)", response_description="List jobs matching filters")
def list_jobs(query: Optional[str] = None, location: Optional[str] = None, skills: Optional[List[str]] = None):
    filtered = []
    for job in jobs.values():
        match = True
        if query:
            if query.lower() not in (job["title"].lower() + job["description"].lower()):
                match = False
        if location:
            if location.lower() != job["location"].lower():
                match = False
        if skills:
            if not all(skill.lower() in [s.lower() for s in job["skills"]] for skill in skills):
                match = False
        if match:
            filtered.append(Job(**job))
    return filtered

# PUBLIC_INTERFACE
@jobs_router.get("/{job_id}", response_model=Job, summary="Get job by ID")
def get_job(job_id: int):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return Job(**job)

# PUBLIC_INTERFACE
@jobs_router.put("/{job_id}", response_model=Job, summary="Update job")
def update_job(job_id: int, update: JobCreate, current_user: dict = Depends(get_current_user)):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["posted_by"] != current_user["email"]:
        raise HTTPException(status_code=403, detail="Cannot update job not posted by you")
    updated = job.copy()
    updated.update(update.dict())
    jobs[job_id] = updated
    return Job(**updated)

# PUBLIC_INTERFACE
@jobs_router.delete("/{job_id}", status_code=204, summary="Delete job")
def delete_job(job_id: int, current_user: dict = Depends(get_current_user)):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["posted_by"] != current_user["email"]:
        raise HTTPException(status_code=403, detail="Cannot delete job not posted by you")
    del jobs[job_id]
    return

# === ROUTER: APPLICATIONS ===
applications_router = APIRouter(prefix="/applications", tags=["applications"])

# PUBLIC_INTERFACE
@applications_router.post("/", response_model=Application, status_code=201, summary="Apply for a job")
def apply_for_job(application: ApplicationBase, current_user: dict = Depends(get_current_user)):
    global last_app_id
    if current_user["role"] != "jobseeker":
        raise HTTPException(status_code=403, detail="Only job seekers can apply")
    if application.seeker_email != current_user["email"]:
        raise HTTPException(status_code=403, detail="You can only apply as yourself")
    job = jobs.get(application.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Check if already applied by this seeker
    for app_item in applications.values():
        if app_item["job_id"] == application.job_id and app_item["seeker_email"] == current_user["email"]:
            raise HTTPException(status_code=400, detail="Already applied to this job")
    last_app_id += 1
    new_app = Application(
        id=last_app_id,
        job_id=application.job_id,
        seeker_email=current_user["email"],
        cover_letter=application.cover_letter,
        status="pending",
        applied_at=datetime.utcnow()
    )
    applications[last_app_id] = new_app.dict()
    return new_app

# PUBLIC_INTERFACE
@applications_router.get("/my", response_model=List[Application], summary="List applications (jobseeker)")
def my_applications(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "jobseeker":
        raise HTTPException(status_code=403, detail="Only job seekers can view their applications")
    return [Application(**a) for a in applications.values() if a["seeker_email"] == current_user["email"]]

# PUBLIC_INTERFACE
@applications_router.get("/for-job/{job_id}", response_model=List[Application], summary="List applications for a job (employer)")
def applications_for_job(job_id: int, current_user: dict = Depends(get_current_user)):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["posted_by"] != current_user["email"]:
        raise HTTPException(status_code=403, detail="Only the employer who posted the job can review applications")
    return [Application(**a) for a in applications.values() if a["job_id"] == job_id]

# PUBLIC_INTERFACE
@applications_router.put("/{app_id}/review", response_model=Application, summary="Employer reviews application status")
def review_application(app_id: int, review: ApplicationReview, current_user: dict = Depends(get_current_user)):
    app_item = applications.get(app_id)
    if not app_item:
        raise HTTPException(status_code=404, detail="Application not found")
    job = jobs.get(app_item["job_id"])
    if not job or job["posted_by"] != current_user["email"]:
        raise HTTPException(status_code=403, detail="Can only review applications for your jobs")
    app_item["status"] = review.status
    applications[app_id] = app_item
    return Application(**app_item)

# === ROUTER: DASHBOARD ===
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# PUBLIC_INTERFACE
@dashboard_router.get("/jobseeker", summary="Job seeker dashboard")
def jobseeker_dashboard(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "jobseeker":
        raise HTTPException(status_code=403, detail="Job seekers only")
    my_apps = [a for a in applications.values() if a["seeker_email"] == current_user["email"]]
    applied_job_ids = [a["job_id"] for a in my_apps]
    applied_jobs = [jobs[jid] for jid in applied_job_ids if jid in jobs]
    return {
        "user": {"email": current_user["email"], "name": current_user["name"], "role": "jobseeker"},
        "num_applications": len(my_apps),
        "applied_jobs": applied_jobs,
        "applications": my_apps,
    }

# PUBLIC_INTERFACE
@dashboard_router.get("/employer", summary="Employer dashboard")
def employer_dashboard(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "employer":
        raise HTTPException(status_code=403, detail="Employers only")
    posted_jobs = [job for job in jobs.values() if job["posted_by"] == current_user["email"]]
    job_ids = [job["id"] for job in posted_jobs]
    all_apps = [a for a in applications.values() if a["job_id"] in job_ids]
    return {
        "user": {"email": current_user["email"], "name": current_user["name"], "role": "employer"},
        "num_jobs_posted": len(posted_jobs),
        "jobs": posted_jobs,
        "num_applications": len(all_apps),
        "applications": all_apps,
    }

# === HEALTHCHECK ROOT ENDPOINT ===
# PUBLIC_INTERFACE
@app.get("/", tags=["health"], summary="Health Check")
def health_check():
    """Simple health check endpoint."""
    return {"message": "Healthy"}

# === REGISTER ROUTERS ===
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(dashboard_router)
