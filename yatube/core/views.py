from http import HTTPStatus

from django.shortcuts import render


def page_not_found(request, exception):
    template = 'core/404.html'
    context = {'path': request.path}
    status = HTTPStatus.NOT_FOUND
    return render(request, template, context, status)


def csrf_failure(request, reason=''):
    template = 'core/403csrf.html'
    return render(request, template)
