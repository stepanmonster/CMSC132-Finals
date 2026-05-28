import math

class Length:
	whole = 5
	precision = 16	#length of precision
	fraction = precision-whole-1
	dec_place = 2
	instrxn = 16+precision
	opAddr = 7
	opMode = 4
	operand = opAddr+opMode
	@staticmethod
	def trimDec(value,places=dec_place):
		return round(float(value),places)
	def addZeros(value,strlen,lead=True):
		toBin = type(value)!=type(str())
		if toBin:
			value = bin(int(value)).replace("0b","")
		if lead:
			return value.zfill(strlen)
		return value+"".zfill(strlen-len(value))

class BinaryFraction:
	@staticmethod
	def idec2bin(idec,ibinlen=Length.fraction):
		ibin = Length.addZeros(idec*(2**ibinlen),ibinlen)
		return ibin
	def ibin2dec(ibin):
		istart = ibin.find(".")
		return int(ibin[istart+1:], 2) / 2.**(len(ibin))

class HalfPrecision:
	@staticmethod
	def hpbin2dec(binum,binlen=Length.whole):
		de = 2**(binlen-1)-1
		s = int(binum[0])
		e = int(binum[1:binlen+1],2)
		f = BinaryFraction.ibin2dec(binum[binlen+1:])
		return Length.trimDec((-1)**s*2**(e-de)*(1+f))
	def hpdec2bin(decnum,binlen=Length.whole):
		if decnum==0:
			return "0"+"0"*binlen+"0"*(Length.fraction)
		de = 2**(binlen-1)-1
		s = 0
		if decnum<0:
			s = 1
		p = int(math.log2(abs(decnum)))
		e = str(bin(p+de))[2:]
		lead = "0"*(binlen-len(e))
		e = lead+e
		f = BinaryFraction.idec2bin(abs(decnum)/(2**p)-1)
		return str(s)+str(e)+str(f)
	def hpbin2bin(bin_str,binlen):
		result = HalfPrecision.hpbin2dec(bin_str)
		result = Length.addZeros(result,binlen)
		return result
	def bin2hpbin(bin_str):
		result = int(bin_str,2)
		result = HalfPrecision.hpdec2bin(result)
		return result

find_fake = False
if find_fake:
	fake_cntr = 0
	dec = 0
	max_e = 11
	max_num = 2**max_e
	too_much_fake = max_num
	total_num = max_num*10**dec
	print_cmp = True
	print_errors = True
	print_innerrors = False
	round_fake = False
	for i in range(max_num):
		for j in range(10**dec):
			k = round(i+j*1.0/(10**dec),dec)
			fake_k = HalfPrecision.hpbin2dec(HalfPrecision.hpdec2bin(k))
			if round_fake:
				fake_k = round(fake_k,dec)
			if k!=fake_k:
				if print_cmp:
					print(f"{k} {fake_k}")
				fake_cntr += 1
		if too_much_fake<=fake_cntr:
			break
		if print_innerrors:
			fake_pcnt = fake_cntr/total_num
			print(f"From 0 to {max_num}, for {dec} decimal places:")
			print(str(fake_cntr)+" errors out of "+str(total_num)+" ("+str(round(fake_pcnt*100,int(max_e/5)))+"%)")
	if print_errors:
		fake_pcnt = fake_cntr/total_num
		print(f"From 0 to {max_num}, for {dec} decimal places:")
		print(str(fake_cntr)+" errors out of "+str(total_num)+" ("+str(round(fake_pcnt*100,int(max_e/5)))+"%)")

