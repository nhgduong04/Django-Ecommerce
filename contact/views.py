from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.http import JsonResponse
from django.shortcuts import redirect, render


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message_content = request.POST.get('message', '').strip()

        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

        if not all([name, email, subject, message_content]):
            error_message = 'Please complete all required fields before submitting.'
            if is_ajax:
                return JsonResponse({'success': False, 'message': error_message}, status=400)
            messages.error(request, error_message)
            return redirect('contact')

        to_email = getattr(settings, 'CONTACT_EMAIL', None) or settings.EMAIL_HOST_USER
        mail_subject = f'Contact Form: {subject}'
        mail_body = (
            'You have received a new contact request.\n\n'
            f'Name: {name}\n'
            f'Email: {email}\n'
            f'Subject: {subject}\n\n'
            f'Message:\n{message_content}'
        )

        try:
            email_message = EmailMessage(
                subject=mail_subject,
                body=mail_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email],
                reply_to=[email],
            )
            email_message.send(fail_silently=False)
        except Exception:
            error_message = 'Sorry, we could not send your message right now. Please try again later.'
            if is_ajax:
                return JsonResponse({'success': False, 'message': error_message}, status=500)
            messages.error(request, error_message)
            return redirect('contact')

        success_message = 'Your message has been sent successfully. We will contact you soon.'
        if is_ajax:
            return JsonResponse({'success': True, 'message': success_message})

        messages.success(request, success_message)
        return redirect('contact')

    return render(request, 'contact.html')