$(function () {
    var $contactForm = $("#contactForm");

    if (!$contactForm.length) {
        return;
    }

    function getCsrfToken($form) {
        var formToken = $form.find("input[name='csrfmiddlewaretoken']").val();
        if (formToken) {
            return formToken;
        }

        var cookieMatch = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return cookieMatch ? decodeURIComponent(cookieMatch[1]) : "";
    }

    $("#contactForm input, #contactForm textarea").jqBootstrapValidation({
        preventSubmit: true,
        submitError: function ($form, event, errors) {
        },
        submitSuccess: function ($form, event) {
            event.preventDefault();

            var name = $("input#name").val();
            var email = $("input#email").val();
            var subject = $("input#subject").val();
            var message = $("textarea#message").val();
            var endpoint = $form.attr("action");
            var csrfToken = getCsrfToken($form);
            var $button = $("#sendMessageButton");

            $button.prop("disabled", true);

            $.ajax({
                url: endpoint,
                type: "POST",
                dataType: "json",
                cache: false,
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken
                },
                data: {
                    csrfmiddlewaretoken: csrfToken,
                    name: name,
                    email: email,
                    subject: subject,
                    message: message
                },
                success: function (response) {
                    var successMessage = (response && response.message) || "Your message has been sent.";

                    $('#success').html("<div class='alert alert-success'>");
                    $('#success > .alert-success').html("<button type='button' class='close' data-dismiss='alert' aria-hidden='true'>&times;")
                        .append("</button>");
                    $('#success > .alert-success').append($("<strong>").text(successMessage));
                    $('#success > .alert-success').append('</div>');
                    $('#contactForm').trigger("reset");
                },
                error: function (xhr) {
                    var responseMessage = xhr.responseJSON && xhr.responseJSON.message;
                    var defaultMessage = "Sorry " + name + ", it seems that our mail server is not responding. Please try again later!";

                    $('#success').html("<div class='alert alert-danger'>");
                    $('#success > .alert-danger').html("<button type='button' class='close' data-dismiss='alert' aria-hidden='true'>&times;")
                        .append("</button>");
                    $('#success > .alert-danger').append($("<strong>").text(responseMessage || defaultMessage));
                    $('#success > .alert-danger').append('</div>');
                },
                complete: function () {
                    setTimeout(function () {
                        $button.prop("disabled", false);
                    }, 1000);
                }
            });
        },
        filter: function () {
            return $(this).is(":visible");
        },
    });

    $("a[data-toggle=\"tab\"]").click(function (e) {
        e.preventDefault();
        $(this).tab("show");
    });

    $('#name').focus(function () {
        $('#success').html('');
    });
});
