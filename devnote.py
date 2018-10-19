#---------------------------------------------------------------------------#
#   The develope note                                                       #
#---------------------------------------------------------------------------#
#   Contain improve proposals/working progressions                          #
#---------------------------------------------------------------------------#

#---------------------------------------------------------------------------#
#   Improve Proposals                                                       #
#---------------------------------------------------------------------------#
#   Add ranking publish rule description.                                   #
#       --                                                                  #
#                                                                           #
#   Flexible logger                                                         #
#       add filehandler and remove with                                     #
#       'logger.removeHandler'.                                             #
#                                                                           #
#   Use enum to replace string mode selection                               #
#       Providing mode listing and lint compatibility.                      #
#---------------------------------------------------------------------------#

#---------------------------------------------------------------------------#
#   Login required functions                                                #
#       Requires login cookies to verify, otherwise raises HTTPS 401 Error. #
#       Once cookie is acquired, no further html parsing is needed.         #
#---------------------------------------------------------------------------#
#   General illust:                                                         #
#       https://www.pixiv.net/ajax/illust/<illust_id>                       #
#   Ugoira metadata:                                                        #
#       https://www.pixiv.net/ajax/illust/<ugoira_id>/ugoira_meta           #
#---------------------------------------------------------------------------#
#   Pixiv login requires a "post_key" hidden inside login page.             #
#   A global dictionary recording opened session?                           #
#---------------------------------------------------------------------------#

#---------------------------------------------------------------------------#
#   A class for simple encapsulation?                                       #
#   Just simply collect functions than seperating namespaces.               #
#---------------------------------------------------------------------------#

#---------------------------------------------------------------------------#
#   An extra typehint file?                                                 #
#---------------------------------------------------------------------------#
