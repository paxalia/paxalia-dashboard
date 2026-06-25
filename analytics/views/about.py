from django.shortcuts import render

def about(request):
    context = {
        'active_page': 'about',
        'page_title': 'About',
        'page_subtitle': 'The story behind this dashboard',
    }
    return render(request, 'analytics/about.html', context)