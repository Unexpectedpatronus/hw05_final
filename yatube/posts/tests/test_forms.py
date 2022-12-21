import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Comment, Group, Post

User = get_user_model()
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='author')
        cls.user_not_author = User.objects.create_user(username='not_author')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_slug',
            description='test description'
        )
        cls.post = Post.objects.create(
            text='Тестовый пост',
            pub_date='Тестовая дата',
            author=cls.user,
            group=cls.group,
        )
        cls.comment = Comment.objects.create(
            post=cls.post,
            author=cls.user,
            text='Тестовый комментарий',
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.authorized_client_not_author = Client()
        self.authorized_client_not_author.force_login(self.user_not_author)

    def test_create_post(self):
        """Валидная форма создает запись в Post."""
        posts_count = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.pk,
            'image': uploaded,
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response, reverse(
                'posts:profile', kwargs={'username': f'{self.user.username}'}
            )
        )
        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertTrue(
            Post.objects.filter(
                text=form_data['text'],
                author=self.user,
                group=form_data['group'],
                image='posts/small.gif',
            ).exists()
        )

    def test_edit_post_unauthorized(self):
        """Неавторизованный пользователь хочет отредактировать пост."""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.pk
        }
        response = self.guest_client.post(
            reverse(
                'posts:post_edit', kwargs={'post_id': f'{self.post.pk}'}
            ),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response, f'/auth/login/?next=/posts/{self.post.pk}/edit/')
        self.assertEqual(Post.objects.count(), posts_count)
        self.assertTrue(
            Post.objects.filter(
                id=self.post.id,
                text=self.post.text,
                pub_date=self.post.pub_date,
                author=self.post.author,
                group=self.post.group,
                image=self.post.image,
            ).exists()
        )

    def test_create_post_unauthorized(self):
        """Неавторизованный пользователь хочет создать пост."""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.pk
        }
        response = self.guest_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response, '/auth/login/?next=/create/')
        self.assertEqual(Post.objects.count(), posts_count)

    def test_edit_post_not_author(self):
        """Юзер хочет отредактировать чужой пост."""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.pk,
        }
        response = self.authorized_client_not_author.post(
            reverse(
                'posts:post_edit', kwargs={'post_id': f'{self.post.pk}'}
            ),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response, f'/posts/{self.post.pk}/')
        self.assertEqual(Post.objects.count(), posts_count)
        self.assertTrue(
            Post.objects.filter(
                id=self.post.id,
                text=self.post.text,
                pub_date=self.post.pub_date,
                author=self.post.author,
                group=self.post.group,
                image=self.post.image,
            ).exists()
        )

    def test_edit_post_author(self):
        """Автор хочет отредактировать свой пост."""
        posts_count = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.pk,
            'image': uploaded,
        }
        response = self.authorized_client.post(
            reverse(
                'posts:post_edit', kwargs={'post_id': f'{self.post.pk}'}
            ),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response, f'/posts/{self.post.pk}/'
        )
        self.assertEqual(Post.objects.count(), posts_count)
        self.assertTrue(
            Post.objects.filter(
                id=self.post.id,
                text=form_data['text'],
                pub_date=self.post.pub_date,
                author=self.post.author,
                group=form_data['group'],
            ).exists()
        )

    def test_comment_authorized_client(self):
        """После успешной отправки комментарий появляется на странице поста."""
        form_data = {
            'text': 'Тестовый комментарий',
        }
        comments_count = Comment.objects.count()
        response = self.authorized_client.post(
            reverse(
                'posts:add_comment', kwargs={'post_id': f'{self.post.pk}'}
            ),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(response, f'/posts/{self.post.pk}/')
        self.assertEqual(Comment.objects.count(), comments_count + 1)
        self.assertTrue(
            Comment.objects.filter(text='Тестовый комментарий').exists()
        )

    def test_comment_unauthorized_client(self):
        """Неавторизованный пользователь не может комментировать посты."""
        form_data = {
            'text': 'Тестовый комментарий',
        }
        response = self.guest_client.post(
            reverse(
                'posts:add_comment', kwargs={'post_id': f'{self.post.pk}'}
            ),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, f'/auth/login/?next=/posts/{self.post.pk}/comment/'
        )
