INDICATORS=[
 {'code':'1.16','name':'Early breastfeeding initiation','target':95,'direction':'higher','numerator':'breastfed_1hr','denominator':'deliveries','period':'ratio','module':'nutrition'},
 {'code':'2.4','name':'Under-five stunting assessment','target':10,'direction':'higher','numerator':'measured_unique','denominator':'under5','period':'annual','module':'nutrition'},
 {'code':'2.5','name':'Anaemia at 36 weeks','target':35.5,'direction':'lower','numerator':'anaemic_36','denominator':'hb_checked_36','period':'ratio','module':'nutrition'},
 {'code':'2.6','name':'Vitamin A coverage','target':80,'direction':'higher','numerator':'vitamin_a_unique','denominator':'vitamin_a_population','period':'half','module':'nutrition'},
 {'code':'2.9','name':'Underweight prevalence','target':3.8,'direction':'lower','numerator':'underweight','denominator':'weighed','period':'ratio','module':'nutrition'},
 {'code':'3.31','name':'Wellness clinic attendance','target':20,'direction':'higher','numerator':'wellness_unique','denominator':'wellness_population','period':'annual','module':'wellness'}]
FIELDS={
 'nutrition':[
 ('deliveries','Mothers delivering at facility','Breastfeeding'),('breastfed_1hr','Babies breastfed within 1 hour','Breastfeeding'),('breastfed_3min','Initiated EBF within 3 minutes (template)','Breastfeeding'),('ebf_discharge','Exclusive breastfeeding at discharge','Breastfeeding'),
 ('registrants_male','New registrants — male','Growth monitoring'),('registrants_female','New registrants — female','Growth monitoring'),('weighed','Total under-five children weighed (attendance)','Growth monitoring'),('underweight','Underweight: moderate + severe','Growth monitoring'),('underweight_severe','Severely underweight','Growth monitoring'),('measured_unique','New unique under-five children measured this year','Growth monitoring'),('vitamin_a_unique','New unique children 6–59 months dosed this half-year','Vitamin A'),('vitamin_a_6_11','Doses to children 6–11 months (all visits)','Vitamin A'),('vitamin_a_12_59','Doses to children 12–59 months (all visits)','Vitamin A'),
 ('hb_checked_36','Women with Hb checked at 36 weeks','Anaemia'),('anaemic_36','Women at 36 weeks with Hb <11 g/dL','Anaemia'),('severe_anaemic_36','Women at 36 weeks with Hb <7 g/dL','Anaemia'),('ifa3','Women given IFA 3','Anaemia'),('ifa6','Women given IFA 6','Anaemia'),('iycf_registered','New C-IYCF registrants','IYCF & rehabilitation'),('iycf_visited','Children visited at least once','IYCF & rehabilitation'),('sam_admitted','SAM admissions','IYCF & rehabilitation'),('sam_cured','SAM cured','IYCF & rehabilitation'),('sam_deaths','SAM deaths','IYCF & rehabilitation')],
 'wellness':[
 ('wellness_unique','New unique eligible attendees this year','Attendance'),('visits','Total wellness visits (including repeat visits)','Attendance'),('male','Male visits','Attendance'),('female','Female visits','Attendance'),('bp_screened','Blood pressure screenings','Screening & follow-up'),('glucose_screened','Blood glucose screenings','Screening & follow-up'),('bmi_screened','BMI assessments','Screening & follow-up'),('counselled','Nutrition / lifestyle counselling','Screening & follow-up'),('referred','Clients referred','Screening & follow-up'),('diabetes_opd','Diabetes OPD cases — descriptive only','OPD context'),('hypertension_opd','Hypertension OPD cases — descriptive only','OPD context'),('total_opd','Total OPD attendance','OPD context')]}

def calculate(definition,numerator,denominator,month,has_data=True):
 d=definition
 expected=d['target']*(month/12 if d['period']=='annual' else (((month-1)%6+1)/6) if d['period']=='half' else 1)
 value=100*numerator/denominator if has_data and denominator and denominator>0 else None
 if value is None: status='not_configured' if d['code']=='3.31' and not denominator else 'no_data'
 else:
  met=value<=expected if d['direction']=='lower' else value>=expected
  status='achieved' if met else 'below_target'
 from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
 rounding=ROUND_CEILING if d['direction']=='higher' else ROUND_FLOOR
 def count(percent):
  return int((Decimal(str(denominator))*percent/100).to_integral_value(rounding=rounding)) if denominator and denominator>0 else None
 full=Decimal(str(d['target']))
 elapsed=Decimal(month)/12 if d['period']=='annual' else Decimal((month-1)%6+1)/6 if d['period']=='half' else Decimal(1)
 return {**d,'has_data':has_data,'target_count':count(full),'expected_count':count(full*elapsed),'numerator':numerator,'denominator':denominator,'value':round(value,2) if value is not None else None,'expected':round(expected,2),'status':status}

def validate_counts(module,data):
 allowed={x[0] for x in FIELDS[module]}
 if set(data)-allowed: raise ValueError('Unknown reporting field')
 if any(type(v) is not int or v<0 or v>10000000 for v in data.values()):raise ValueError('Counts must be non-negative whole numbers')
 pairs=[('breastfed_1hr','deliveries'),('breastfed_3min','breastfed_1hr'),('ebf_discharge','deliveries'),('underweight','weighed'),('underweight_severe','underweight'),('anaemic_36','hb_checked_36'),('severe_anaemic_36','anaemic_36')]
 if module=='wellness':pairs=[('wellness_unique','visits'),('referred','visits'),('counselled','visits'),('bp_screened','visits'),('glucose_screened','visits'),('bmi_screened','visits')]
 for a,b in pairs:
  if data.get(a,0)>data.get(b,0):raise ValueError(f'{a} cannot exceed {b}')
 if module=='wellness' and data.get('male',0)+data.get('female',0)!=data.get('visits',0):raise ValueError('Male + female visits must equal total visits')
