"""Form widgets that keep learning material out of the raw ``/media/`` route.

Django's :class:`~django.forms.ClearableFileInput` renders the file it is bound
to as ``Currently: <a href="field.url">name</a>``. For library resources,
assignment attachments and student submissions that ``field.url`` is a guarded
``/media/`` path: it always 404s and it discloses the storage layout, so it must
never be printed. :class:`MaterialFileInput` renders the current file as plain
text instead and links it to the protected, inline-only viewer.
"""

from django import forms
from django.urls import NoReverseMatch


class MaterialFileInput(forms.ClearableFileInput):
    """A clearable file input that never renders a raw storage URL.

    Subclasses set ``view_url_attr`` to the name of the model property that
    returns the authenticated, inline-only URL for the field. The clear
    checkbox is preserved; only the link target changes.
    """

    # Lives in the academics app so the default form renderer (which searches
    # app template directories) can find it without a custom FORM_RENDERER.
    template_name = 'partials/material_file_input.html'

    #: model property holding the protected, inline-only URL
    view_url_attr = None

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget = context['widget']
        widget['protected_url'] = self._protected_url(value)
        # Show only the file name. Leaving a FieldFile in the context would let
        # a template that is not the one above print ``value.url`` anyway, so
        # the FieldFile is replaced by a plain string.
        current = widget['value']
        widget['value'] = current.name.rsplit('/', 1)[-1] if current else ''
        widget['value_text'] = ''
        return context

    def _protected_url(self, value):
        """Reverse the model's view URL for the currently stored file."""
        getter = getattr(getattr(value, 'instance', None), self.view_url_attr or '', None)
        if not callable(getter):
            return ''
        try:
            return getter() or ''
        except NoReverseMatch:
            # An unsaved instance has no pk to reverse against.
            return ''


class AttachmentFileInput(MaterialFileInput):
    """File input for ``academics.models.Assignment.attachment``."""

    view_url_attr = 'attachment_view_url'


class SubmissionFileInput(MaterialFileInput):
    """File input for ``academics.models.StudentAssignment.submission_file``."""

    view_url_attr = 'submission_view_url'