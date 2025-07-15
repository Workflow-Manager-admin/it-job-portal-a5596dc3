# IT Job Portal Backend

This is the backend for the IT Job Portal, built with FastAPI. It provides RESTful APIs for user authentication (job seekers and employers), job posting and searching, job application management, and user dashboards.

---

## Table of Contents

- [Features](#features)
- [Setup](#setup)
- [Running the API Server](#running-the-api-server)
- [Testing](#testing)
- [API Endpoints](#api-endpoints)
  - [Auth](#auth)
  - [Jobs](#jobs)
  - [Applications](#applications)
  - [Dashboards](#dashboards)
- [Usage Notes](#usage-notes)
- [OpenAPI / Docs](#openapi--docs)

---

## Features

- **User authentication** for both job seekers and employers (JWT)
- **Job search, filter, and detailed retrieval**
- **Job posting, editing, and deletion** (Employer only)
- **Applying to jobs** (Job Seeker only)
- **Dashboards** for tracking posted jobs and job applications
- **CORS enabled** for frontend integration

---

## Setup

1. **Python**  
   Requires Python 3.9+

2. **Clone and install dependencies:**
   ```bash
   cd job_portal_backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   
3. **(Optional) Environment Variables**

   By default, the JWT secret is hardcoded for development. For production, set `JWT_SECRET` as an environment variable.

---

## Running the API Server

Start the FastAPI server (default: http://localhost:8000):

```bash
uvicorn src.api.main:app --reload
```

---

## Testing

Run tests with:

```bash
pytest
```

*Note: The sample implementation uses in-memory data, so state will reset between runs.*

---

## API Endpoints

All endpoints require and return JSON contents.

### Auth

| Endpoint              | Method | Purpose                    | Auth Required | Payload Model           |
|-----------------------|--------|----------------------------|---------------|------------------------|
| /auth/register/jobseeker | POST | Register as Job Seeker   | No            | JobSeekerRegister      |
| /auth/register/employer | POST | Register as Employer      | No            | EmployerRegister       |
| /auth/login             | POST | Login (jobseeker/employer)| No            | UserLogin              |
| /auth/token             | POST | OAuth2 login (form-data)  | No            | OAuth2PasswordRequestForm |

### Jobs

| Endpoint         | Method | Purpose                 | Auth Required | Who               |
|------------------|--------|------------------------|---------------|-------------------|
| /jobs/           | POST   | Post new job           | Yes           | Employer only     |
| /jobs/           | GET    | List/search jobs       | No            | Anyone            |
| /jobs/{job_id}   | GET    | Get job details        | No            | Anyone            |
| /jobs/{job_id}   | PUT    | Edit/Update job        | Yes           | Employer (owner)  |
| /jobs/{job_id}   | DELETE | Delete job             | Yes           | Employer (owner)  |

#### Job Filter Parameters:
- `query` (in title or description, optional)
- `location` (optional)
- `skills` (list, optional)

### Applications

| Endpoint                             | Method | Purpose                              | Auth Required        | Who                  |
|-------------------------------------- |--------|--------------------------------------|----------------------|----------------------|
| /applications/                       | POST   | Apply to job                         | Yes                  | Job Seeker only      |
| /applications/my                     | GET    | List my applications                 | Yes                  | Job Seeker           |
| /applications/for-job/{job_id}       | GET    | Applications for specific job        | Yes                  | Employer (owner)     |
| /applications/{app_id}/review        | PUT    | Review/change application status     | Yes                  | Employer (owner)     |

### Dashboards

| Endpoint                  | Method | Description               | Who           |
|---------------------------|--------|---------------------------|---------------|
| /dashboard/jobseeker      | GET    | View jobseeker dashboard  | Job Seeker    |
| /dashboard/employer       | GET    | View employer dashboard   | Employer      |

---

## Usage Notes

- The backend currently uses in-memory data stores (no database); it's suitable for demo or testing.
- All endpoints (except registration, login, jobs listing) require JWT Bearer tokens in the `Authorization` header.
- CORS is enabled for all origins for local dev.
- Example requests can be made with [httpie](https://httpie.io/), curl, or via the interactive Swagger docs.

---

## OpenAPI / Docs

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Redoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## License

MIT License.

