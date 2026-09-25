# ADOM Institute

A comprehensive Django-based school management platform for ADOM Institute with modern features including real-time notifications, role-based access control, and comprehensive analytics.

## Features

### Core Features
- **User Management**: Multi-role system (Super Admin, Administrator, Teacher, Student, Parent, Accountant)
- **Student Management**: Enrollment, profiles, attendance tracking, academic records
- **Teacher Management**: Staff profiles, subject assignments, performance tracking
- **Academic Management**: Exams, grades, assignments, report cards
- **Fee Management**: Fee structures, payments, receipts, discounts
- **Attendance System**: Daily attendance, leave management, analytics
- **Communication**: Real-time messaging, announcements, notifications
- **Timetable Management**: Class schedules, room assignments, conflict detection
- **Analytics & Reports**: Performance analytics, financial reports, custom reports

### Technical Features
- **RESTful API**: Complete API with Django REST Framework
- **Real-time Notifications**: WebSocket support with Django Channels
- **Role-Based Access Control**: Granular permissions system
- **Two-Factor Authentication**: Enhanced security for staff accounts
- **PDF Generation**: Report cards, receipts, certificates
- **Email & SMS Integration**: Automated notifications
- **File Management**: Document uploads, media handling
- **Background Tasks**: Celery integration for heavy operations
- **Database**: PostgreSQL with optimized queries
- **Caching**: Redis for performance optimization

## Technology Stack

- **Backend**: Django 4.2.7, Django REST Framework
- **Database**: PostgreSQL
- **Real-time**: Django Channels, Redis
- **Background Tasks**: Celery, Redis
- **File Storage**: AWS S3 (optional) / Local
- **PDF Generation**: WeasyPrint
- **Email**: SMTP with django-anymail
- **SMS**: Twilio integration
- **API Documentation**: drf-yasg (Swagger/ReDoc)
- **Authentication**: JWT, Token-based
- **Frontend**: HTML, CSS, JavaScript (Bootstrap/Tailwind ready)

## Installation

### Prerequisites
- Python 3.8+
- PostgreSQL
- Redis
- Virtual environment (recommended)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd adom-institute
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   Create a `.env` file in the project root:
   ```env
   # Django Settings
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   
   # Database
   DB_NAME=adom_institute
   DB_USER=postgres
   DB_PASSWORD=your-password
   DB_HOST=localhost
   DB_PORT=5432
   
   # Email Configuration
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-app-password
   DEFAULT_FROM_EMAIL=noreply@adominstitute.com
   
   # Redis Configuration
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   
   # Optional: AWS S3
   USE_S3=False
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   AWS_STORAGE_BUCKET_NAME=your-bucket-name
   ```

5. **Database Setup**
   ```bash
   # Create PostgreSQL database
   createdb adom_institute
   
   # Run migrations
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create Superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Load Sample Data (Optional)**
   ```bash
   python manage.py loaddata fixtures/sample_data.json
   ```

8. **Start Development Server**
   ```bash
   # Start Redis (required for WebSockets and Celery)
   redis-server
   
   # Start Celery worker (in new terminal)
   celery -A adom worker -l info
   
   # Start Celery beat (in new terminal, for scheduled tasks)
   celery -A adom beat -l info
   
   # Start Django development server
   python manage.py runserver
   ```

## Usage

### Access Points
- **Admin Panel**: http://localhost:8000/admin/
- **API Documentation**: http://localhost:8000/swagger/
- **Main Application**: http://localhost:8000/

### User Roles

1. **Super Admin**
   - Full system access
   - User management
   - System configuration
   - Analytics and reports

2. **Administrator**
   - Student and teacher management
   - Academic year setup
   - Fee structure management
   - General administration

3. **Teacher**
   - Attendance marking
   - Grade entry
   - Assignment creation
   - Student communication

4. **Student**
   - View timetable
   - Submit assignments
   - Check grades
   - View attendance

5. **Parent**
   - Monitor child's progress
   - View attendance
   - Fee payments
   - Communication with teachers

6. **Accountant**
   - Fee management
   - Payment processing
   - Financial reports
   - Receipt generation

## API Usage

### Authentication
```bash
# Get authentication token
curl -X POST http://localhost:8000/api/v1/accounts/api/token/
     -H "Content-Type: application/json"
     -d '{"email": "user@example.com", "password": "password"}'

# Use token in requests
curl -H "Authorization: Token your-token-here" 
     http://localhost:8000/api/v1/students/
```

### Example API Endpoints
- `GET /api/v1/students/` - List students
- `POST /api/v1/students/` - Create student
- `GET /api/v1/attendance/` - List attendance records
- `POST /api/v1/fees/payments/` - Create payment
- `GET /api/v1/analytics/reports/` - Generate reports

## Development

### Project Structure
```
adom/  # Django project root
├── accounts/          # User management, authentication
├── students/          # Student profiles, enrollment
├── teachers/          # Teacher management, subjects
├── academics/         # Exams, grades, assignments
├── fees/             # Fee management, payments
├── attendance/       # Attendance tracking
├── communication/    # Messages, notifications
├── timetable/        # Class schedules
├── analytics/        # Reports, analytics
├── adom/  # Main project settings
├── templates/        # HTML templates
├── static/          # CSS, JS, images
├── media/           # Uploaded files
└── requirements.txt
```

### Adding New Features
1. Create models in appropriate app
2. Run `python manage.py makemigrations`
3. Create serializers for API
4. Add views and URLs
5. Update admin interface
6. Add tests
7. Update documentation

### Testing
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test accounts

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

## Deployment

### Production Setup
1. Set `DEBUG=False` in settings
2. Configure production database
3. Set up static file serving
4. Configure email settings
5. Set up SSL certificate
6. Configure backup system

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Contact: admin@adominstitute.com

## Roadmap

- [ ] Mobile app development
- [ ] Advanced analytics dashboard
- [ ] Integration with external LMS
- [ ] Multi-language support
- [ ] Advanced reporting features
- [ ] Parent portal enhancements
- [ ] Student portal improvements
- [ ] Teacher dashboard enhancements
# adom-institute
