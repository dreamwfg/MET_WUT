from django.contrib import admin
from django import forms
from django.shortcuts import render
from users.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'first_name',
        'last_name',
        'email',
        'phone',
        'payment_status',
        'attendance',
        'proctor',
        'decision',
        'slate_status'
    )
    search_fields = ('first_name', 'last_name', 'email', 'proctor', 'passport_id')
    list_filter = ('decision', 'payment_status', 'proctor', 'slate_status')
    ordering = ('-id',)

    # ---- custom bulk action ----
    actions = ['assign_proctor']

    @admin.action(description="Assign selected users to a specific proctor")
    def assign_proctor(self, request, queryset):
        """Bulk-assign a proctor name to all selected users."""
        class ProctorForm(forms.Form):
            proctor_name = forms.CharField(label="Proctor name", max_length=100)

        if 'apply' in request.POST:
            form = ProctorForm(request.POST)
            if form.is_valid():
                proctor_name = form.cleaned_data['proctor_name']
                updated = queryset.update(proctor=proctor_name)
                self.message_user(request, f"{updated} users updated with proctor '{proctor_name}'.")
                return None
        else:
            form = ProctorForm(initial={'_selected_action': queryset.values_list('id', flat=True)})

        # Render the small confirm form
        return render(
            request,
            'admin/assign_proctor.html',  # Django will look for this template
            {'form': form, 'objects': queryset},
        )

    # ---- hide system fields ----
    exclude = (
        'password',
        'last_login',
        'is_staff',
        'is_superuser',
        'groups',
        'user_permissions',
        'is_active',
        'username',
    )
