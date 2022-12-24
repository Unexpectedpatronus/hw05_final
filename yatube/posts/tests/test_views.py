import shutil
import tempfile

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from mixer.backend.django import mixer

from ..models import Comment, Follow, Group, Post

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)
NUMBER_OF_TESTED_PAGES: int = 13

User = get_user_model()


class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='author')
        cls.user_not_author = User.objects.create_user(username='not_author')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            text='Тестовый пост',
            author=cls.user,
            group=cls.group,
        )
        cls.comment = Comment.objects.create(
            post=cls.post,
            author=cls.user,
            text='Тестовый комментарий'
        )

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.authorized_client_not_author = Client()
        self.authorized_client_not_author.force_login(self.user_not_author)

    def test_cache_index_page(self):
        """Проверяем работу кэша главной страницы"""
        response = self.authorized_client_not_author.get('/')
        cached_response_content = response.content
        Post.objects.create(text='Второй пост', author=self.user)
        response = self.authorized_client_not_author.get('/')
        self.assertEqual(cached_response_content, response.content)
        cache.clear()
        response = self.authorized_client_not_author.get('/')
        self.assertNotEqual(cached_response_content, response.content)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        # Собираем в словарь пары "имя_html_шаблона: reverse(name)"
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list', kwargs=(
                {'slug': f'{self.post.group.slug}'})): 'posts/group_list.html',
            reverse('posts:profile', kwargs=(
                {'username': f'{self.user}'})): 'posts/profile.html',
            reverse('posts:post_detail', kwargs=(
                {'post_id': f'{self.post.id}'})): 'posts/post_detail.html',
            reverse('posts:post_edit', kwargs=(
                {'post_id': f'{self.post.id}'})): 'posts/create_post.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse('posts:follow_index'): 'posts/follow.html',
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_home_page_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:index'))
        first_object = response.context['page_obj'][0]
        post_text_0 = first_object.text
        post_author_0 = first_object.author
        post_group_0 = first_object.group
        self.assertEqual(post_text_0, 'Тестовый пост')
        self.assertEqual(post_author_0, self.user)
        self.assertEqual(post_group_0, self.group)

    def test_group_list_show_correct_context(self):
        """Шаблон group_list сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse(
                'posts:group_list', kwargs={'slug': f'{self.post.group.slug}'}
            )
        )
        first_object = response.context['page_obj'][0]
        post_text_0 = first_object.text
        post_author_0 = first_object.author
        post_group_0 = first_object.group
        self.assertEqual(post_text_0, 'Тестовый пост')
        self.assertEqual(post_author_0, self.user)
        self.assertEqual(post_group_0, self.group)
        self.assertTrue(response.context.get('group'))
        group_object = response.context['group']
        self.assertEqual(group_object, self.group)

    def test_profile_show_correct_context(self):
        """Шаблон profile сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse(
            'posts:profile',
            kwargs=({'username': f'{self.user}'})))
        first_object = response.context['page_obj'][0]
        post_text_0 = first_object.text
        post_author_0 = first_object.author
        post_group_0 = first_object.group
        self.assertEqual(post_text_0, 'Тестовый пост')
        self.assertEqual(post_author_0, self.user)
        self.assertEqual(post_group_0, self.group)
        self.assertTrue(response.context.get('profile'))
        profile_object = response.context['profile']
        self.assertEqual(profile_object, self.user)

    def test_post_detail_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.id})
        )
        first_object = response.context['post']
        post_author_0 = first_object.author
        post_text_0 = first_object.text
        post_group_0 = first_object.group
        self.assertEqual(post_author_0, self.user)
        self.assertEqual(post_text_0, 'Тестовый пост')
        self.assertEqual(post_group_0, self.group)
        expected = forms.fields.CharField
        form_field = response.context.get('form').fields.get('text')
        self.assertIsInstance(form_field, expected)
        comment_object = response.context['comments'][0]
        comment_author_0 = comment_object.author
        comment_text_0 = comment_object.text
        self.assertEqual(comment_text_0, 'Тестовый комментарий')
        self.assertEqual(comment_author_0, self.user)

    def test_create_post_show_correct_context(self):
        """Шаблон create_post сформирован с правильным контекстом."""
        response = self.authorized_client_not_author.get(
            reverse('posts:post_create'))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
            'image': forms.fields.ImageField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)
        self.assertFalse(response.context.get('is_edit'))

    def test_post_edit_show_correct_context(self):
        """Шаблон create_post для редактирования
        сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse(
                'posts:post_edit', kwargs={'post_id': f'{self.post.id}'}
            )
        )
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
            'image': forms.fields.ImageField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)
        self.assertTrue(response.context.get('is_edit'))


class PaginatorViewsTest(TestCase):
    """Тестируется paginator."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Author')
        cls.user_1 = User.objects.create_user(username='TestUser')
        cls.group = Group.objects.create(
            title='test group',
            slug='test_slug',
            description='test description',
        )
        post_list = []
        for i in range(NUMBER_OF_TESTED_PAGES):
            new_post = Post(
                text=f'#{i} Текст тестового поста #{i}',
                author=cls.user,
                group=cls.group,
            )
            post_list.append(new_post)
        cls.post_list = Post.objects.bulk_create(post_list)

    def setUp(self):
        cache.clear()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user_1)

    def test_first_page_contains_ten_records(self):
        TEN_POSTS = 10
        THREE_POSTS = 3
        Follow.objects.create(
            user=self.user_1,
            author=self.user
        )
        first_page = {
            reverse('posts:index'): TEN_POSTS,
            (reverse('posts:group_list',
                     kwargs={'slug': self.group.slug})): TEN_POSTS,
            (reverse('posts:profile',
                     kwargs={'username': self.user})): TEN_POSTS,
            (reverse('posts:index') + '?page=2'): THREE_POSTS,
            (reverse('posts:group_list',
                     kwargs={'slug': self.group.slug}) + '?page=2'
             ): THREE_POSTS,
            (reverse('posts:profile',
                     kwargs={'username': self.user}) + '?page=2'
             ): THREE_POSTS,
            reverse('posts:follow_index'): TEN_POSTS,
            reverse('posts:follow_index') + '?page=2': THREE_POSTS
        }
        for value, expected in first_page.items():
            with self.subTest(value=value):
                response = self.authorized_client.get(value)
                self.assertEqual(
                    len(response.context['page_obj']), expected)


class FollowTest(TestCase):
    def setUp(self):
        self.guest_client = Client()
        self.user = User.objects.create_user(username='auth')
        self.user_2 = User.objects.create_user(username='auth_2')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_user_following_many_users(self):
        follow_count = Follow.objects.count()
        self.authorized_client.get(reverse(
            'posts:profile_follow',
            kwargs={'username': self.user_2.username}))
        self.assertEqual(Follow.objects.count(), follow_count + 1)
        self.assertTrue(
            Follow.objects.filter(user=self.user, author=self.user_2).exists()
        )

    def test_user_unfollowing_many_users(self):
        self.authorized_client.get(reverse(
            'posts:profile_follow',
            kwargs={'username': self.user_2.username}))
        follow_count = Follow.objects.count()
        user_unfollow = Follow.objects.filter(
            user=self.user, author=self.user_2
        )
        user_unfollow.delete()
        self.assertEqual(Follow.objects.count(), follow_count - 1)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ImagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='TestUser')
        cls.group = mixer.blend(Group, slug='test-slug')
        cls.small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=cls.small_gif,
            content_type='image/gif'
        )
        cls.post = mixer.blend(
            Post, author=cls.user, group=cls.group, image=cls.uploaded
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()

    def test_image_index_group_profile(self):
        """Тест картинки на страницах: index, group_list, profile."""
        links = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': self.group.slug}),
            reverse('posts:profile', kwargs={'username': self.post.author}),
        ]
        for link in links:
            with self.subTest(link):
                response = self.guest_client.get(link)
                image_post = response.context['page_obj'][0]
                self.assertEqual(image_post.image, self.post.image)

    def test_image_post_detail(self):
        """Тест картинки на странице post_detail."""
        response = self.guest_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.pk})
        )
        image_post = response.context['post']
        self.assertEqual(image_post.image, self.post.image)
