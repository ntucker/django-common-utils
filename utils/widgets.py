from django import forms
from django.forms.util import to_current_timezone


class DateTimeRangeWidget(forms.MultiWidget):
    def __init__(self, attrs=None, format=None, time_widget=None):
        if time_widget is None:
            time_widget = forms.DateTimeInput
        widgets = (time_widget(attrs=attrs, format=format),
                   time_widget(attrs=attrs, format=format))
        super(DateTimeRangeWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return list(map(to_current_timezone, [value.lower, value.upper]))
        return [None, None]
