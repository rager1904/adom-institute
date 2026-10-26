"""Public course content, shared by the catalogue and course detail pages.

Keep unconfirmed fees and durations empty. Proposed teaching outlines are
explicitly identified on the public page until approved by the institute.
"""
from django.utils.text import slugify


CATEGORIES = (
    ('ai', 'AI & Digital Skills'),
    ('finance', 'Finance & Forex'),
    ('accounting', 'Accounting & Business'),
    ('ict', 'Computer & ICT'),
)


def course(title, category, image, summary, *, duration='', fee='', outcomes=(), outline=()):
    return {
        'slug': slugify(title), 'title': title, 'category': category,
        'category_label': dict(CATEGORIES)[category],
        'image': f'images/course-catalog/{image}.png', 'summary': summary,
        'duration': duration, 'fee': fee, 'level': 'Advanced' if title.startswith('Advanced ') else 'Beginner',
        'credential': 'Certificate course' if duration else 'Practical training',
        'outcomes': outcomes,
        'outline': outline,
        'requirements': ('Basic computer skills', 'Access to a laptop or smartphone'),
    }


COURSES = [
    course('AI & ChatGPT for Beginners', 'ai', 'ai',
           'Learn to use AI tools confidently for everyday tasks, work and business.',
           duration='5 days', fee='K750',
           outcomes=('Write clear, effective prompts', 'Use AI for practical work tasks',
                     'Create and improve everyday content', 'Check AI outputs and protect sensitive data'),
           outline=(
               ('Day 1: Introduction to AI and ChatGPT', 'Explore what AI can do, its limitations and how to use ChatGPT.'),
               ('Day 2: Writing effective prompts', 'Practise giving clear instructions, adding context and refining responses.'),
               ('Day 3: AI for everyday productivity', 'Use guided exercises to draft content, summarise information and plan tasks.'),
               ('Day 4: Practical applications and responsible use', 'Check accuracy, recognise bias and protect personal and business information.'),
               ('Day 5: Guided project and review', 'Apply the skills in a practical task and review your learning.'),
           )),
    course('Forex Trading for Beginners', 'finance', 'forex',
           'Understand forex markets, trading concepts and the importance of managing risk.',
           duration='5 days', fee='K750',
           outcomes=('Understand currency pairs and market terminology', 'Read basic price charts',
                     'Recognise trading risks', 'Practise planning with a demonstration account'),
           outline=(('Introduction to forex markets', 'Learn market terminology and how currency pairs work.'),
                    ('Charts and market analysis', 'Explore basic chart reading and approaches to analysis.'),
                    ('Risk awareness and practice', 'Discuss risk management and practise with simulated examples.'))),
    course('Practical Bookkeeping', 'accounting', 'bookkeeping',
           'Develop practical bookkeeping skills for small businesses and organisations.',
           outcomes=('Understand basic bookkeeping records', 'Record everyday transactions',
                     'Organise financial documents', 'Prepare simple financial summaries')),
    course('Excel & Data Analysis', 'ai', 'excel',
           'Learn to organise, analyse and visualise data using Microsoft Excel.',
           outcomes=('Organise data in worksheets', 'Use practical formulas', 'Summarise data', 'Create clear charts')),
    course('Basic Computer Literacy', 'ict', 'computer',
           'Build essential computer skills for work, business and everyday life.',
           outcomes=('Navigate a computer confidently', 'Manage files and folders',
                     'Use common office applications', 'Practise safer internet use')),
    course('Digital Marketing', 'ict', 'marketing',
           'Explore practical ways to promote a business through digital channels.',
           outcomes=('Identify your target audience', 'Plan useful digital content',
                     'Understand digital channels', 'Review basic campaign results')),
]

# Preserve discovery of programmes listed on the previous public courses page.
ADDITIONAL_COURSES = {
    'ai': ('Prompt Engineering', 'AI for Business', 'AI for Teachers', 'AI for Accounting', 'Digital Office Skills'),
    'finance': ('Advanced Forex Trading', 'Financial Literacy', 'Investment Fundamentals', 'Budgeting',
                'Cash Flow', 'Financial Management'),
    'accounting': ('Accounting with Excel', 'ZRA Taxation & Online Returns', 'PAYE', 'NAPSA', 'NHIMA',
                   'Business Registration', 'Entrepreneurship', 'Business Management', 'Taxation', 'Payroll',
                   'Business startup training', 'Company registration workshops', 'Accounting software training',
                   'Odoo & POS user training', 'Inventory management', 'Payroll administration',
                   'Debt collection skills', 'Small-business financial management'),
    'ict': ('Microsoft Word', 'Microsoft Excel', 'Microsoft PowerPoint', 'Internet Skills',
            'Computer Applications', 'Introduction to Business Software'),
}
for category, titles in ADDITIONAL_COURSES.items():
    for title in titles:
        COURSES.append(course(title, category, {'ai': 'ai', 'finance': 'forex', 'accounting': 'bookkeeping', 'ict': 'computer'}[category],
                              f'Practical {title.lower()} training. Contact our team to discuss the programme and next intake.'))

COURSES_BY_SLUG = {item['slug']: item for item in COURSES}
