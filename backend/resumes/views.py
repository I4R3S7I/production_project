from rest_framework import viewsets
from users.models import User
from .models import Resume
from .serializers import ResumeSerializer
from .permissions import ResumePermission

class ResumeViewSet(viewsets.ModelViewSet):
    queryset = Resume.objects.all()
    serializer_class = ResumeSerializer
    permission_classes = (ResumePermission,)

    def get_queryset(self):
        user = self.request.user

        if user.role in (User.Role.ADMIN, User.Role.HR):
            return Resume.objects.all()

        return Resume.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
