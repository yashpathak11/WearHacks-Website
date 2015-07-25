from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Fieldset, Div, Field
from crispy_forms.bootstrap import FormActions, StrictButton


from registration.models import Registration

class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = (
                'first_name',
                'last_name',
                'gender',
                'is_student',
                'school',
                'email',
                'github',
                'linkedin',
                'food_restrictions',
                # 'tshirt_size',
                'is_returning',
                'is_hacker',
                'resume',
                'waiver'
            )

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'registration-form'
        self.helper.form_method = 'post'
        self.helper.form_action = 'register'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-3'
        self.helper.field_class = 'col-lg-6'


        self.helper.layout = Layout(
            Fieldset(
                'General Information',
                'first_name',
                'last_name',
                'gender',
                'email',
            ),
            Fieldset(
                'Tell us a bit about yourself.',
                Field('is_student', label="Are you a student?"),
                'is_returning',
                'is_hacker',
                'school',
            ),
            Fieldset(
                'Experience',
                'github',
                'linkedin',
                'resume',
            ),
            Fieldset(
                'Almost there!',
                'food_restrictions',
                'waiver',
            ),
            FormActions(
                StrictButton('Sign me up', name='register', 
                    css_class='btn-primary pull-right', css_id="register")
            )
        )


        # self.helper.add_layout(
        #     FormActions(
        #         StrictButton('Sign me up', name='register', 
        #     css_class='btn-success'), id="register"))
        # self.helper.add_input(Submit('register', 'Submit'))
