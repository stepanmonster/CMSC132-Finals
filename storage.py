from bin_convert import HalfPrecision, Length
import copy

class Storage:
	def __init__(self, data={}):
		self.data = copy.deepcopy(data)
	def load(self, address):
		if type(address)==type(str()) and len(address)==Length.precision:
			address = HalfPrecision.hpbin2dec(address)
		value = self.data[address]
		if len(value)!=Length.precision:
			return value
		value = HalfPrecision.hpbin2dec(value)
		return value
	def store(self,address,value):
		if type(address)==type(str()) and len(address)==Length.precision:
			address = HalfPrecision.hpbin2dec(address)
		if type(value)==type(str()):
			self.data[address] = value
		else:
			self.data[address] = HalfPrecision.hpdec2bin(value)
	def setStorage(self,stolen):
		for i in range(stolen):
			try:
				self.load(i)
			except:
				self.store(i,0)
	def dispStorage(self):
		for k,v in self.data.items():
			print(f"{k}: {v}")
	@staticmethod
	def setVariable(var,name,addr,value):
		variable.store(name,addr)
		var.store(addr,value)
	def setVariables(name,base,stolen=0):
		if len(name)>1:
			stolen = len(name)
		for i in range(stolen):
			if len(name)>1:
				variable.store(name[i],base+i)
			else:
				variable.store(name+str(i+1),base+i)
			
memory = Storage()
register = Storage()
variable = Storage()
ir = 9
xr = 77
br = 9
bm = 57
fm = 65
pm = 69
Storage.setVariable(register,"BR",br,ir)
Storage.setVariable(register,"XR",br+1,xr)
Storage.setVariable(register,"ACC",br+2,0)
Storage.setVariable(register,"IR",br+3,ir)
Storage.setVariable(register,"PC",br+4,ir+1)
Storage.setVariable(register,"JR",br+5,0)
Storage.setVariable(register,"CR",br+6,0)
#register.dispStorage()
var_reglen = 8
Storage.setVariables("R",1,var_reglen)	#R1 to R8
var_blocklen = 8
Storage.setVariables("B",bm,var_blocklen)	#B1 to B8
var_funcblocklen = 4
Storage.setVariables("F",fm,var_funcblocklen)	#F1 to F4
var_funcparamlen = 8
Storage.setVariables("P",pm,var_funcparamlen)	#P1 to P8
var_mem = "ABCDEFGH"
Storage.setVariables(var_mem,1,var_reglen)	#A - H
reg_len = 32
register.setStorage(reg_len)
mem_len = 128
memory.setStorage(mem_len)
variable.data["MSG"] = {}
variable.data["MI"] = 0;
#variable.dispStorage()
#register.dispStorage()
#memory.dispStorage()
"""
Storage:
Variable		Storage for special values in register and memory (variables, blocks, specialialized registers,etc.)
						-	Contains 18-bit HalfPrecision binary format (accurate upto 2^13 or 8192 for integers only)
Memory			Storage that mimics the computer memory with 128 slots (contains 35-bit instruction, 18-bit HalfPrecision values)
Registers		Storage that mimics the computer register with 32 slots (contains only 18-bit HalfPrecision values)

Memmory:
1-8 		Variables								(A-H)
9-56 		Instructions						(Y)
57-64 	Main Blocks							(B)
65-68 	Subprogram Block				(F)
69-76		Subprogram Parameters		(P)
77-100 	Arrays									(X)
101-116	Indirect Addresses
117-127 Extra Memory Storage
0				Special

Register
1-8		Variables							(R)
9-20	Specialized
	9		Based Register				(BR)
	10	Index Register				(XR)
	11	Accumulator						(ACC) - non-functional
	12	Instruction Register	(IR)
	13	Program Counter				(PC)
	14	Jump Register					(JR)
	15	Call Register					(CR)
21-31	Extra Register Storage
0			Special
"""


