

def voFromFqan(fqan):
	components = fqan.split('/')[1:]
	components = filter(lambda x: not x.endswith('=NULL'), components)
	return '/'.join(components)
	


class UserCredentials(object):
	def __init__(self, env):
		# Default
		self.user_dn   = None
		self.voms_cred = []
		self.vos       = []
		
		# Try first GRST_ variables
		grstIndex = 0
		grstEnv = 'GRST_CRED_AURI_%d' % grstIndex
		while grstEnv in env:
			cred = env[grstEnv]
			
			if cred.startswith('dn:') and self.user_dn is None:
				self.user_dn = cred[3:]
			elif cred.startswith('fqan:'):
				fqan = cred[5:]
				vo   = voFromFqan(fqan)
				self.voms_cred.append(fqan)
				self.vos.append(vo)
				
			
			grstIndex += 1
			grstEnv = 'GRST_CRED_AURI_%d' % grstIndex
		
		# If not, try with regular SSL_
		if 'SSL_CLIENT_S_DN' in env:
			self.user_dn = env['SSL_CLIENT_S_DN']
		