from django import forms


class ContactoParroquiaForm(forms.Form):
    ROL_CHOICES = [
        ("", "Seleccioná tu rol"),
        ("parroco", "Párroco"),
        ("secretaria", "Secretaría"),
        ("diacono", "Diácono"),
        ("agente", "Agente pastoral"),
        ("otro", "Otro"),
    ]

    nombre = forms.CharField(max_length=100, label="Nombre")
    email = forms.EmailField(label="Email")
    rol = forms.ChoiceField(choices=ROL_CHOICES, label="Rol en la parroquia")
    mensaje = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=1000,
        label="Mensaje",
    )
    acepta_contacto = forms.BooleanField(
        required=True,
        label="Acepto que Parroguía se comunique conmigo para verificar esta información",
    )

    def clean_rol(self):
        rol = self.cleaned_data.get("rol")
        if not rol:
            raise forms.ValidationError("Seleccioná tu rol.")
        return rol
