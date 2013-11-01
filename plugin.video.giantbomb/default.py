from resources.lib.giantbomb import GiantBomb
from resources.lib.requesthandler import RequestHandler

import time
import urllib
import xbmcaddon
import xbmcplugin
import xbmcgui

addon_id = int(sys.argv[1])
my_addon = xbmcaddon.Addon('plugin.video.giantbomb')

def update_api_key(api_key):
    my_addon.setSetting('api_key', api_key)

gb = GiantBomb(my_addon.getSetting('api_key') or None, update_api_key)
handler = RequestHandler(sys.argv[0])

xbmcplugin.setContent(addon_id, 'movies')
xbmcplugin.setPluginFanart(addon_id, my_addon.getAddonInfo('fanart'))

@handler.handler
def link_account(first_run=False):
    dialog = xbmcgui.Dialog()
    nolabel = 'Skip' if first_run else 'Cancel'
    ok = dialog.yesno("Let's do this.",
                      'To link your account, visit',
                      'www.giantbomb.com/xbmc to get a link code.',
                      'Enter this code on the next screen.',
                      yeslabel='Next', nolabel=nolabel)

    while ok:
        keyboard = xbmc.Keyboard('', 'Enter your link code', False)
        keyboard.doModal()
        if keyboard.isConfirmed():
            link_code = keyboard.getText().upper()
            if gb.get_api_key(link_code):
                dialog.ok('Success!', 'Your account is now linked!',
                          'If you are a premium member,',
                          'you should now have premium privileges.')
                return True
            else:
                ok = dialog.yesno("We're really sorry, but...",
                                  'We could not link your account.',
                                  'Make sure the code you entered is correct',
                                  'and try again.',
                                  yeslabel='Try again', nolabel='Cancel')
        else:
            ok = False

    # If we got here, we gave up trying to link the account.
    return False

@handler.handler
def unlink_account():
    dialog = xbmcgui.Dialog()
    ok = dialog.yesno('Oh no!',
                      'Are you sure you want to unlink your account?',
                      yeslabel='Unlink', nolabel='Cancel')
    if ok:
        my_addon.setSetting('api_key', '')

@handler.default_handler
def categories():
    if my_addon.getSetting('first_run') == 'true':
        if not my_addon.getSetting('api_key'):
            link_account(first_run=True)
        my_addon.setSetting('first_run', 'false')

    data = gb.query('video_types')
    # Count up the total number of categories; add one for "Latest" and one more
    # for "Search".
    total = data['number_of_total_results'] + 2

    # Add the "Latest" pseudo-category
    url = handler.build_url({ 'mode': 'videos' })
    li = xbmcgui.ListItem('Latest', iconImage='DefaultFolder.png')
    li.setProperty('fanart_image', my_addon.getAddonInfo('fanart'))
    xbmcplugin.addDirectoryItem(handle=addon_id, url=url,
                                listitem=li, isFolder=True,
                                totalItems=total)

    # Add all the real categories
    for category in data['results']:
        name = category['name']
        mode = 'endurance' if category['id'] == 5 else 'videos'
        url = handler.build_url({
                'mode': mode,
                'gb_filter': 'video_type:%d' % category['id']
                })
        li = xbmcgui.ListItem(category['name'], iconImage='DefaultFolder.png')
        li.setProperty('fanart_image', my_addon.getAddonInfo('fanart'))
        xbmcplugin.addDirectoryItem(handle=addon_id, url=url,
                                    listitem=li, isFolder=True,
                                    totalItems=total)

    # Add the "Search" pseudo-category
    url = handler.build_url({ 'mode': 'search' })
    li = xbmcgui.ListItem('Search', iconImage='DefaultFolder.png')
    li.setProperty('fanart_image', my_addon.getAddonInfo('fanart'))
    xbmcplugin.addDirectoryItem(handle=addon_id, url=url,
                                listitem=li, isFolder=True,
                                totalItems=total)

    xbmcplugin.endOfDirectory(addon_id)

def list_videos(data, page, plugin_params=None):
    quality_mapping = ['low_url', 'high_url', 'hd_url']
    quality = quality_mapping[ int(my_addon.getSetting('video_quality')) ]

    menu = []

    # Make sure this value is an int, since Giant Bomb currently returns this as
    # a string.
    total = int(data['number_of_total_results'])
    if page == 'all':
        this_page = total
    else:
        this_page = len(data['results'])

        if page > 0:
            url = handler.build_url(dict(page=page-1, **plugin_params))
            menu.append(('Previous page',
                         'Container.Update(' + url + ', replace)'))
        if (page+1) * 100 < total:
            url = handler.build_url(dict(page=page+1, **plugin_params))
            menu.append(('Next page', 'Container.Update(' + url + ', replace)'))

    for video in data['results']:
        name = video['name']
        date = time.strptime(video['publish_date'], '%Y-%m-%d %H:%M:%S')
        duration = video['length_seconds']

        # Build the URL for playing the video
        remote_url = video.get(quality, video['high_url'])
        if quality == 'hd_url' and 'hd_url' in video:
            # XXX: This assumes the URL already has a query string!
            remote_url += '&' + urllib.urlencode({ 'api_key': gb.api_key })

        li = xbmcgui.ListItem(name, iconImage='DefaultVideo.png',
                              thumbnailImage=video['image']['super_url'])
        li.addStreamInfo('video', { 'duration': duration })
        li.setInfo('video', infoLabels={
                'title': name,
                'plot': video['deck'],
                'date': time.strftime('%d.%m.%Y', date),
                })
        li.setProperty('IsPlayable', 'true')
        li.addContextMenuItems(menu)
        li.setProperty('fanart_image', my_addon.getAddonInfo('fanart'))
        xbmcplugin.addDirectoryItem(handle=addon_id, url=remote_url,
                                    listitem=li, totalItems=this_page)

@handler.handler
def videos(gb_filter=None, page='0'):
    api_params = { 'sort': 'publish_date:desc' }
    plugin_params = { 'mode': 'videos' }

    if gb_filter:
        api_params['filter'] = plugin_params['gb_filter'] = gb_filter

    if page == 'all':
        data = gb.query('videos', api_params)
        list_videos(data, page, plugin_params)
        # Make sure this value is an int, since Giant Bomb currently returns
        # this as a string.
        total = int(data['number_of_total_results'])

        for offset in range(100, total, 100):
            api_params['offset'] = offset
            data = gb.query('videos', api_params)
            list_videos(data, page, plugin_params)
    else:
        page = int(page)
        api_params['offset'] = page * 100
        data = gb.query('videos', api_params)
        list_videos(data, page, plugin_params)

    xbmcplugin.endOfDirectory(addon_id)

@handler.handler
def endurance(gb_filter):
    runs = [ 'Chrono Trigger', 'Deadly Premonition', 'Persona 4',
             'The Matrix Online' ]

    for run in runs:
        url = handler.build_url({ 'mode': 'videos', 'page': 'all',
                                  'gb_filter': gb_filter + ',name:%s' % run })
        li = xbmcgui.ListItem(run, iconImage='DefaultFolder.png')
        xbmcplugin.addDirectoryItem(handle=addon_id, url=url,
                                    listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(addon_id)

@handler.handler
def search(query=None, page='0'):
    page = int(page)

    if query is None:
        keyboard = xbmc.Keyboard('', 'Search', False)
        keyboard.doModal()
        if keyboard.isConfirmed():
            query = keyboard.getText()
        else:
            xbmc.executebuiltin('Action(ParentDir)')
            return

    data = gb.query('search', { 'resources': 'video', 'query': query,
                                 'offset': page*100 })
    list_videos(data, page, { 'mode': 'search', 'query': query })
    xbmcplugin.endOfDirectory(addon_id)

handler.run(sys.argv[2])
