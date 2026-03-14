from django.shortcuts import render

# Create your views here.
def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        # Here you can handle the form data, e.g., save it to the database or send an email
        
    return render(request, 'contact.html')