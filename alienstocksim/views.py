from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render
from django.shortcuts import render, redirect
from alienstocksim.forms import LoginForm, RegisterForm

# Create your views here.
def login_action(request):
    context = {}

    # Just display the registration form if this is a GET request.
    if request.method == 'GET':
        context['form'] = LoginForm()
        return render(request, 'alienstocksim/login.html', context)

    # Creates a bound form from the request POST parameters
    # And makes the form available in the request context dictionary.
    form = LoginForm(request.POST)

    # Validates the form.
    if not form.is_valid():
        context['form'] = form
        return render(request, 'alienstocksim/login.html', context)

    new_user = authenticate(username=form.cleaned_data['username'],
                            password=form.cleaned_data['password'])

    login(request, new_user)
    return redirect('global')


def register_action(request):
    context = {}

    # Just display the registration form if this is a GET request.
    if request.method == 'GET':
        # initialize a new form object (unbound form)
        context['form'] = RegisterForm()
        return render(request, 'alienstocksim/register.html', context)

    # Creates a bound form from the request POST parameters
    # and makes the form available in the request context dictionary
    form = RegisterForm(request.POST)

    # Validates the form.
    if not form.is_valid():
        # the form object has errors built into it
        context['form'] = form
        return render(request, 'alienstocksim/register.html', context)

    # At this point, the form data is valid.  Register and login the user.
    new_user = User.objects.create_user(username=form.cleaned_data['username'],
                                        password=form.cleaned_data['password'],
                                        email=form.cleaned_data['email'],
                                        first_name=form.cleaned_data['first_name'],
                                        last_name=form.cleaned_data['last_name'])

    new_user = authenticate(username=form.cleaned_data['username'],
                            password=form.cleaned_data['password'])

    login(request, new_user)
    return redirect('global')

@login_required
def logout_action(request):
    logout(request)
    return redirect('login')