"""
HTML form fields
"""

import abc

from pyrobot.compat import with_metaclass, string_types
from .. import helpers

class ValueMeta(type):
    """Metaclass that creates a value property on class creation. Classes
    with this metaclass should define _get_value and optionally _set_value
    methods.

    """
    def __init__(cls, name, bases, dct):
        cls.value = property(
            getattr(cls, '_get_value', None),
            getattr(cls, '_set_value', None),
        )
        super(ValueMeta, cls).__init__(name, bases, dct)

class FieldMeta(ValueMeta, abc.ABCMeta):
    """Multiply inherit from ValueMeta and ABCMeta; classes with this metaclass
    are automatically assigned a value property and can use methods fromABCMeta
    (e.g. abstractmethod).

    """
    pass

class BaseField(with_metaclass(FieldMeta)):
    """Abstract base class for form fields."""

    def __init__(self, parsed):
        """Construct form field from HTML string or BeautifulSoup tag.
        
        :param parsed: String or BeautifulSoup tag

        """
        self._parsed = helpers.ensure_soup(parsed)
        self.name = self._get_name(parsed)

    def _get_name(self, parsed):
        return parsed.get('name')

    # Different form fields may serialize their values under different keys.
    # The default key is 'data'. See Form::serialize for more.
    _serialize_key = 'data'
    def serialize(self):
        return {self.name: self.value}

    # Property methods
    def _get_value(self):
        return self._value if self._value else ''

    def _set_value(self, value):
        self._value = value

class Input(BaseField):

    def __init__(self, parsed):
        super(Input, self).__init__(parsed)
        self.value = self._parsed.get('value')

class FileInput(BaseField):

    def _set_value(self, value):
        if hasattr(value, 'read'):
            self._value = value
        elif isinstance(value, string_types):
            self._value = open(value)
        else:
            raise ValueError('Value must be a file object or file path')

    # Serialize value to 'files' key for compatibility with file attachments
    # in requests.
    _serialize_key = 'files'
    def serialize(self):
        return {self.name: self.value}

class MultiOptionField(BaseField):

    def __init__(self, parsed):
        super(MultiOptionField, self).__init__(parsed)
        self.options, self.labels, initial = self._get_options(parsed)
        self._set_initial(initial)

    @abc.abstractmethod
    def _get_options(self, parsed):
        return [], [], []

    def _set_initial(self, initial):
        self._value = None
        try:
            self.value = initial[0]
        except IndexError:
            pass

    def _value_to_index(self, value):
        if value in self.options:
            return self.options.index(value)
        if value in self.labels:
            index = self.labels.index(value)
            if index not in self.labels[index:]:
                return index
        raise ValueError

    # Property methods
    def _get_value(self):
        if self._value is None:
            return ''
        return self.options[self._value]

    def _set_value(self, value):
        self._value = self._value_to_index(value)

class MultiValueField(MultiOptionField):

    def _set_initial(self, initial):
        self.value = initial

    # Property methods
    def _get_value(self):
        return [
            self.options[idx]
            for idx in self._value
        ]

    def _set_value(self, value):
        if not isinstance(value, list):
            value = [value]
        self._value = [
            self._value_to_index(item)
            for item in value
        ]

    # List-like methods
    def append(self, value):
        index = self._value_to_index(value)
        if index in self._value:
            raise ValueError
        self._value.append(index)
        self._value.sort()

    def remove(self, value):
        index = self._value_to_index(value)
        self._value.remove(index)

class FlatOptionField(MultiOptionField):

    def _get_name(self, parsed):
        return parsed[0].get('name')

    def _get_options(self, parsed):
        options, labels, initial = [], [], []
        for option in parsed:
            value = option.get('value')
            checked = option.get('checked')
            options.append(value)
            labels.append(
                option.next.string
                if isinstance(option.next, string_types)
                else None
            )
            if checked is not None:
                initial.append(value)
        return options, labels, initial

class NestedOptionField(MultiOptionField):

    def _get_options(self, parsed):
        options, labels, initial = [], [], []
        for option in parsed.find_all('option'):
            value = option.get('value')
            selected = option.get('selected')
            options.append(value)
            labels.append(option.text)
            if selected is not None:
                initial.append(value)
        return options, labels, initial

class Textarea(Input):

    def __init__(self, parsed):
        super(Textarea, self).__init__(parsed)
        self.value = self._parsed.text.rstrip('\r').rstrip('\n')

class Checkbox(FlatOptionField, MultiValueField):
    pass

class Radio(FlatOptionField, MultiOptionField):
    pass

class Select(NestedOptionField, MultiOptionField):
    def _set_initial(self, initial):
        """If no option is selected initially, select the first option.

        """
        super(Select, self)._set_initial(initial)
        if not self._value:
            self.value = self.options[0]

class MultiSelect(NestedOptionField, MultiValueField):
    pass
