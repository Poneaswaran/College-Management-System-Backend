class TenantService:
    @staticmethod
    def get_tenant_key(user=None):
        if not user:
            return None
        department = getattr(user, "department", None)
        if department and getattr(department, "code", None):
            return department.code
        return None

    @staticmethod
    def apply_department_scope(queryset, user=None, field_name="department"):
        if not user:
            return queryset

        role = getattr(getattr(user, "role", None), "code", None)
        if role in {"ADMIN"}:
            return queryset

        department = getattr(user, "department", None)
        if department is None:
            return queryset

        return queryset.filter(**{f"{field_name}_id": department.id})
