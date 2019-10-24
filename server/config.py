cfg = {
    'faceDetThreshold': '0.7'
}

ubuntu_cfg = cfg.copy()
ubuntu_cfg['log_file'] = '/home/dev/faceRec/server/mesg.log'
ubuntu_cfg['ssl_crt'] = 'ssl/faceRec.crt'
ubuntu_cfg['ssl_key'] = 'ssl/faceRec.key'

win_cfg = cfg.copy()

win_cfg['log_file'] = 'C:\\Telesens\\web\\faceRec\\client\\mesg.log'
win_cfg['ssl_crt'] = ''
win_cfg['ssl_key'] = ''