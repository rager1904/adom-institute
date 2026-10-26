# Public course pages verification

The course catalogue and course-detail content follow the approved designs.
Following review, both pages inherit the homepage navigation and footer through
`public/base_public.html`. Course CSS is scoped to `.course-content` so it cannot
override shared navigation, footer or site colours.

## Verification performed

- Course catalogue: category filters, search, empty results and pagination.
- Course details: all configured slugs resolve; unknown courses return 404.
- Course details: outline expansion, section links and course-specific WhatsApp URLs.
- Desktop, tablet and mobile layouts inspected in the in-app browser.
- Shared header and footer confirmed on both course routes.
- Courses navigation remains active on detail pages.
- Six course tests and six tuition tests passed.
- Django system checks and static collection passed.

## Content decisions

- Only AI and Forex have confirmed five-day K750 offers; other fees/durations
  display an enquiry prompt.
- Proposed outlines and requirements remain labelled as subject to confirmation.
- Pagination preserves access to previously listed training programmes.
- No WhatsApp messages were sent during testing.

## Deployment

Run `python manage.py migrate` for tuition enquiry storage and
`python manage.py collectstatic --noinput` for public page assets.

Screenshots and approved mockups were reviewed locally and are not included in
the repository. This document records completed checks rather than an automated
browser test suite.
