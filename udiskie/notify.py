"""
Udiskie notification daemon.
"""

__all__ = ['Notify']


class Notify(object):

    """
    Notification tool.

    Can be connected to udisks daemon in order to automatically issue
    notifications when system status has changed.
    """

    def __init__(self, notify, mounter, timeout=None):
        """
        Initialize notifier.

        A notify service such as pynotify or notify2 should be passed in.
        """
        self._notify = notify
        self._mounter = mounter
        self._timeout = timeout
        # pynotify does not store hard references to the notification
        # objects. When a signal is received and the notification does not
        # exist anymore, no handller will be called. Therefore, we need to
        # prevent these notifications from being destroyed by storing
        # references (note, notify2 doesn't need this):
        self._notifications = []
        # Subscribe all enabled events to the daemon:
        udisks = mounter.udisks
        for event in ['device_mounted', 'device_unmounted',
                      'device_locked', 'device_unlocked',
                      'device_added', 'device_removed',
                      'job_failed']:
            if self._enabled(event):
                udisks.connect(event, getattr(self, event))

    # event handlers:
    def device_mounted(self, device):
        label = device.id_label
        mount_path = device.mount_paths[0]
        notification = self._notification(
            'device_mounted',
            'Device mounted',
            '%s mounted on %s' % (label, mount_path),
            'drive-removable-media')
        if self._mounter._browser:
            # Show a 'Browse directory' button in mount notifications.
            # Note, this only works with some libnotify services.
            def on_browse(notification, action):
                self._mounter.browse(device)
            notification.add_action('browse', "Browse directory", on_browse)
            # Need to store a reference (see above) only if there is a
            # signal connected:
            notification.connect('closed', self._notifications.remove)
            self._notifications.append(notification)
        notification.show()

    def device_unmounted(self, device):
        label = device.id_label
        self._notification(
            'device_unmounted',
            'Device unmounted',
            '%s unmounted' % (label,),
            'drive-removable-media').show()

    def device_locked(self, device):
        device_file = device.device_presentation
        self._notification(
            'device_locked',
            'Device locked',
            '%s locked' % (device_file,),
            'drive-removable-media').show()

    def device_unlocked(self, device):
        device_file = device.device_presentation
        self._notification(
            'device_unlocked',
            'Device unlocked',
            '%s unlocked' % (device_file,),
            'drive-removable-media').show()

    def device_added(self, device):
        device_file = device.device_presentation
        if (device.is_drive or device.is_toplevel) and device_file:
            self._notification(
                'device_added',
                'Device added',
                'device appeared on %s' % (device_file,),
                'drive-removable-media').show()

    def device_removed(self, device):
        device_file = device.device_presentation
        if (device.is_drive or device.is_toplevel) and device_file:
            self._notification(
                'device_removed',
                'Device removed',
                'device disappeared on %s' % (device_file,),
                'drive-removable-media').show()

    def job_failed(self, device, action, message):
        device_file = device.device_presentation or device.object_path
        if message:
            text = 'failed to %s %s:\n%s' % (action, device_file, message)
        else:
            text = 'failed to %s device %s.' % (action, device_file,)
        notification = self._notification('job_failed',
                                          'Job failed', text,
                                          'drive-removable-media')
        try:
            retry = getattr(self._mounter, action)
        except AttributeError:
            pass
        else:
            # Show a 'Retry' button in mount notifications.
            # Note, this only works with some libnotify services.
            def on_retry(notification, action):
                retry(device)
            notification.add_action('retry', "Retry", on_retry)
            # Need to store a reference (see above) only if there is a
            # signal connected:
            notification.connect('closed', self._notifications.remove)
            self._notifications.append(notification)
        notification.show()

    def _notification(self, event, summary, message, icon):
        notification = self._notify.Notification(summary, message, icon)
        timeout = self._get_timeout(event)
        if timeout != -1:
            notification.set_timeout(int(timeout * 1000))
        return notification

    def _enabled(self, event):
        return self._get_timeout(event) is not None

    def _get_timeout(self, event):
        if not self._timeout:
            return -1
        try:
            timeout = self._timeout[event]
        except KeyError:
            timeout = self._timeout.get('timeout', -1)
        if timeout in ('', None):
            return None
        try:
            return int(timeout)
        except ValueError:
            return float(timeout)
