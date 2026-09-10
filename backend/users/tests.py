from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from resumes.models import Resume

User = get_user_model()


class AuthLoginTest(APITestCase):
    """Тесты эндпоинта /api/auth/login/ и /api/auth/register/."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='candidate1',
            password='pass123',
            role=User.Role.CANDIDATE,
        )
        cls.login_url = reverse('login')
        cls.register_url = reverse('register')

    def test_login_with_valid_credentials(self):
        response = self.client.post(
            self.login_url,
            {'username': 'candidate1', 'password': 'pass123'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['username'], 'candidate1')
        self.assertEqual(response.data['role'], User.Role.CANDIDATE)
        self.assertTrue(Token.objects.filter(user=self.user).exists())

    def test_login_with_invalid_password(self):
        response = self.client.post(
            self.login_url,
            {'username': 'candidate1', 'password': 'wrong'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('token', response.data)

    def test_register_creates_custom_user(self):
        response = self.client.post(
            self.register_url,
            {
                'username': 'new_candidate',
                'password': 'pass123',
                'email': 'new@example.com',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='new_candidate')
        self.assertEqual(user.role, User.Role.CANDIDATE)
        self.assertEqual(user.email, 'new@example.com')
        self.assertTrue(user.check_password('pass123'))
        self.assertNotIn('password', response.data)

    def test_register_ignores_role_from_payload(self):
        response = self.client.post(
            self.register_url,
            {
                'username': 'hacker',
                'password': 'pass123',
                'role': 'admin'
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='hacker')
        self.assertEqual(user.role, User.Role.CANDIDATE)
        self.assertFalse(user.is_staff)


class ResumeAPITestCase(APITestCase):
    """Данные для матрицы прав /api/resumes/."""

    @classmethod
    def setUpTestData(cls):
        cls.candidate1 = User.objects.create_user(
            username = 'resume_candidate1',
            password = 'pass123',
            role = User.Role.CANDIDATE,
        )
        cls.candidate2 = User.objects.create_user(
            username = 'resume_candidate2',
            password = 'pass123',
            role = User.Role.CANDIDATE,
        )
        cls.hr = User.objects.create_user(
            username = 'hr_manager',
            password = 'pass123',
            role = User.Role.HR,
        )
        cls.admin = User.objects.create_user(
            username = 'admin_user',
            password = 'pass123',
            role = User.Role.ADMIN,
        )

        cls.resume1 = Resume.objects.create(
            user = cls.candidate1,
            position = 'Python Developer',
            experience = '2 years',
        )
        cls.resume2 = Resume.objects.create(
            user = cls.candidate2,
            position = 'C# Developer',
            experience = '3 years',
        )

        cls.list_url = reverse('resume-list')
        cls.detail_url = lambda pk: reverse('resume-detail', args=[pk])
        cls.resume_payload = {
            'position': 'Backend Dev',
            'experience': '1 year',
        }

    def auth_as(self, user):
        self.client.force_authenticate(user=user)

    def list_results(self, response):
        if isinstance(response.data, list):
            return response.data
        return response.data['results']


class ResumeAuthTest(ResumeAPITestCase):
    """Без авторизации: все операции /api/resumes/ -> 401."""

    def test_list_without_auth_returns_401(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_without_auth_returns_401(self):
        response = self.client.get(self.detail_url(self.resume1.pk))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_without_auth_returns_401(self):
        response = self.client.post(
            self.list_url,
            self.resume_payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_without_auth_returns_401(self):
        response = self.client.patch(
            self.detail_url(self.resume1.pk),
            {'position': 'Hacked'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_without_auth_returns_401(self):
        response = self.client.put(
            self.detail_url(self.resume1.pk),
            self.resume_payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_without_auth_returns_401(self):
        response = self.client.delete(self.detail_url(self.resume1.pk))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CandidateResumeTest(ResumeAPITestCase):
    """Кандидат: list/retrieve/create/update — только свои, чужие → 404; delete → 403."""

    def setUp(self):
        self.auth_as(self.candidate1)

    def test_list_shows_only_own_resumes(self):
        response = self.client.get(self.list_url)
        results = self.list_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.resume1.id)

    def test_retrieve_own_resume(self):
        response = self.client.get(self.detail_url(self.resume1.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['position'], 'Python Developer')

    def test_retrieve_other_resume_returns_404(self):
        response = self.client.get(self.detail_url(self.resume2.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_resume(self):
        response = self.client.post(
            self.list_url,
            self.resume_payload,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user'], self.candidate1.id)
        self.assertEqual(
            Resume.objects.filter(user=self.candidate1).count(),
            2,
        )

    def test_patch_own_resume(self):
        response = self.client.patch(
            self.detail_url(self.resume1.pk),
            {'position': 'Senior Python Developer'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resume1.refresh_from_db()
        self.assertEqual(self.resume1.position, 'Senior Python Developer')

    def test_put_own_resume(self):
        response = self.client.put(
            self.detail_url(self.resume1.pk),
            {'position': 'Fullstack Dev', 'experience': '4 years'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resume1.refresh_from_db()
        self.assertEqual(self.resume1.position, 'Fullstack Dev')
        self.assertEqual(self.resume1.experience, '4 years')

    def test_patch_other_resume_returns_404(self):
        response = self.client.patch(
            self.detail_url(self.resume2.pk),
            {'position': 'Hacked'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.resume2.refresh_from_db()
        self.assertEqual(self.resume2.position, 'C# Developer')

    def test_put_other_resume_returns_404(self):
        response = self.client.put(
            self.detail_url(self.resume2.pk),
            self.resume_payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_own_resume_forbidden(self):
        response = self.client.delete(self.detail_url(self.resume1.pk))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Resume.objects.filter(pk=self.resume1.pk).exists())

    def test_delete_other_resume_forbidden_or_not_found(self):
        response = self.client.delete(self.detail_url(self.resume2.pk))
        # has_permission для destroy у кандидата → 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Resume.objects.filter(pk=self.resume2.pk).exists())


class HRResumeTest(ResumeAPITestCase):
    """HR: list/retrieve — все резюме, /create/update/delete → 403."""

    def setUp(self):
        self.auth_as(self.hr)

    def test_list_shows_all_resumes(self):
        response = self.client.get(self.list_url)
        results = self.list_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 2)

    def test_retrieve_any_resume(self):
        response = self.client.get(self.detail_url(self.resume2.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['position'], 'C# Developer')

    def test_create_forbidden(self):
        response = self.client.post(
            self.list_url,
            self.resume_payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_forbidden(self):
        response = self.client.patch(
            self.detail_url(self.resume1.pk),
            {'position': 'Hacked'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.resume1.refresh_from_db()
        self.assertEqual(self.resume1.position, 'Python Developer')

    def test_put_forbidden(self):
        response = self.client.put(
            self.detail_url(self.resume1.pk),
            self.resume_payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_forbidden(self):
        response = self.client.delete(self.detail_url(self.resume1.pk))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Resume.objects.filter(pk=self.resume1.pk).exists())


class AdminResumeTest(ResumeAPITestCase):
    """Админ: полный CRUD по всем резюме."""

    def setUp(self):
        self.auth_as(self.admin)

    def test_list_shows_all_resumes(self):
        response = self.client.get(self.list_url)
        results = self.list_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 2)

    def test_retrieve_any_resume(self):
        response = self.client.get(self.detail_url(self.resume1.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_resume(self):
        response = self.client.post(
            self.list_url,
            {'position': 'Admin Resume', 'experience': 'admin'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user'], self.admin.id)

    def test_patch_any_resume(self):
        response = self.client.patch(
            self.detail_url(self.resume2.pk),
            {'position': 'Updated by Admin'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resume2.refresh_from_db()
        self.assertEqual(self.resume2.position, 'Updated by Admin')

    def test_put_any_resume(self):
        response = self.client.put(
            self.detail_url(self.resume2.pk),
            {'position': 'Put by Admin', 'experience': 'n/a'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resume2.refresh_from_db()
        self.assertEqual(self.resume2.position, 'Put by Admin')

    def test_delete_any_resume(self):
        response = self.client.delete(self.detail_url(self.resume1.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Resume.objects.filter(pk=self.resume1.pk).exists())


class ResumePermissionsMatrixTest(ResumeAPITestCase):
    """
    Сводная матрица прав (list / retrieve / create / update / deдуеу)
    для ролей: Candidate, HR, Admin.
    """

    def test_matrix_list(self):
        cases = [
            (self.candidate1, status.HTTP_200_OK, 1),
            (self.hr, status.HTTP_200_OK, 2),
            (self.admin, status.HTTP_200_OK, 2),
        ]
        for user, expected_status, expected_count in cases:
            with self.subTest(role=user.role):
                self.auth_as(user)
                response = self.client.get(self.list_url)
                results = self.list_results(response)
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(len(results), expected_count)

    def test_matrix_retrieve_own_or_any(self):
        # resume1 принадлежит candidate1
        cases = [
            (self.candidate1, status.HTTP_200_OK),
            (self.candidate2, status.HTTP_404_NOT_FOUND),
            (self.hr, status.HTTP_200_OK),
            (self.admin, status.HTTP_200_OK),
        ]
        for user, expected_status in cases:
            with self.subTest(role=user.role, username=user.username):
                self.auth_as(user)
                response = self.client.get(self.detail_url(self.resume1.pk))
                self.assertEqual(response.status_code, expected_status)

    def test_matrix_create(self):
        cases = [
            (self.candidate1, status.HTTP_201_CREATED),
            (self.hr, status.HTTP_403_FORBIDDEN),
            (self.admin, status.HTTP_201_CREATED),
        ]
        for user, expected_status in cases:
            with self.subTest(role=user.role):
                self.auth_as(user)
                response = self.client.post(
                    self.list_url,
                    {
                        'position': f'Pos-{user.username}',
                        'experience': 'x',
                    },
                    format='json',
                )
                self.assertEqual(response.status_code, expected_status)

    def test_matrix_update(self):
        # правка resume1 (владелец candidate1)
        cases = [
            (self.candidate1, status.HTTP_200_OK),
            (self.candidate2, status.HTTP_404_NOT_FOUND),
            (self.hr, status.HTTP_403_FORBIDDEN),
            (self.admin, status.HTTP_200_OK),
        ]
        for user, expected_status in cases:
            with self.subTest(role=user.role, username=user.username):
                self.auth_as(user)
                response = self.client.patch(
                    self.detail_url(self.resume1.pk),
                    {'position': f'Upd-{user.username}'},
                    format='json',
                )
                self.assertEqual(response.status_code, expected_status)

    def test_matrix_destroy(self):
        # отдельное резюме на каждый кейс, чтобы не мешать друг другу
        cases = [
            (self.candidate1, status.HTTP_403_FORBIDDEN),
            (self.hr, status.HTTP_403_FORBIDDEN),
            (self.admin, status.HTTP_204_NO_CONTENT),
        ]
        for user, expected_status in cases:
            with self.subTest(role=user.role):
                resume = Resume.objects.create(
                    user=self.candidate2,
                    position=f'ToDelete-{user.username}',
                    experience='tmp',
                )
                self.auth_as(user)
                response = self.client.delete(self.detail_url(resume.pk))
                self.assertEqual(response.status_code, expected_status)
                if expected_status == status.HTTP_204_NO_CONTENT:
                    self.assertFalse(
                        Resume.objects.filter(pk=resume.pk).exists(),
                    )
                else:
                    self.assertTrue(
                        Resume.objects.filter(pk=resume.pk).exists(),
                    )