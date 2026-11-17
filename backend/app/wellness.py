"""Aggregate fields transcribed from the supplied Wellness Clinic reporting format."""
SCREENINGS=[('diabetes','Diabetes'),('hypertension','Hypertension'),('height','Height'),('weight','Weight'),('bmi','BMI'),('skin','Skin diseases'),('anaemia','Anaemia'),('others','Others')]
OUTCOMES=[(k,v) for k,v in SCREENINGS if k in ['diabetes','hypertension','bmi','anaemia','others']]
SERVICES=[('counselled','Counselling'),('referred','Referred'),('therapy','Therapy'),('services_others','Others')]
FIELDS=[]
for section,title in [('registrants','Registrants'),('attendance','Attendance')]:
 for key,label in SCREENINGS:
  for col,col_label in [('count',title),('male','Number screened — male'),('female','Number screened — female')]:
   FIELDS.append((f'{section}_{key}_{col}',f'{label} — {col_label}',title))
for key,label in OUTCOMES:
 for sex in ['male','female']:
  for level in ['moderate','severe','normal']:FIELDS.append((f'outcome_{key}_{sex}_{level}',f'{label} — {sex} — {level}','Screening outcomes'))
FIELDS.extend([('therapy','Therapy','Interventions / services'),('services_others','Other services','Interventions / services')])
DETAIL_KEYS={'reporting_date','compiled_by','phone','certified_by','others_description'}|{f'remarks_{k}' for k,_ in SERVICES}
def validate(data):
 for section,_ in [('registrants','Registrants'),('attendance','Attendance')]:
  for key,label in SCREENINGS:
   if data.get(f'{section}_{key}_male',0)+data.get(f'{section}_{key}_female',0)>data.get(f'{section}_{key}_count',0):raise ValueError(f'{section.title()} — {label}: male + female screened cannot exceed the {section} count')
 for key,label in OUTCOMES:
  for sex in ['male','female']:
   if sum(data.get(f'outcome_{key}_{sex}_{level}',0) for level in ['moderate','severe','normal'])>data.get(f'attendance_{key}_{sex}',0):raise ValueError(f'{label} — {sex} outcomes cannot exceed attendance screenings')
