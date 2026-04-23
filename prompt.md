Currently analyze the  partlabeler code that we have component partlabeler in front in backend we have all api ,route, services and queries

what is currently flow of the code is that we upload the warranty data then we  want for dashboard keep our 9 required fields which user for counts and graphs and also we keep other field but keep that in database not this 9 fields are currently we use as you can see in code 

now this warranty data now we want to add drop down in dashboard where we will have 5 feature 
1.warranty data
2.offline rpt data
3.GNOVAC data
4.RFI data
5.e-SQA data

for warranty we have for now but for that the fields will be change for that you can see in folder we have sample csv with schema and some row data for remaining 4 feature

so for the
Offline RPT:
i will what data you will use so for the filters we have 4 filters
mfg months --> use the date column that is first one ex 2026-01-01 so month will be jan-26 like this should be there

mfg qtr --> use the date column only pick the start date and end date according to that derived the quarter months qtrs. will jan26-apr26 like wise take max year for which we want so simple according date need to derived the quater for the 

model ---> use the  model column
MIS ----> use the Defect_Category column

now when mapped the component we search according the concern for the use the PartDefect column for failure search other will be same feature like previous count in side table

for the graphs
vehicle mfg month wise data -----> use the date column that is first one ex 2026-01-01 so month will be jan-26 like this should be there
reporting months wise data ---> give the attribute bar based on the Attribute_Name column where the data empy take it as unknown 
in the KMS wise data ---> guevthe gpeh od shift wise chart use the Shift column 
in the location graph ----> use the bar chart of the which will use the column Location_Name


for the 
GNOVAC:

i will what data you will use so for the filters we have 4 filters
mfg months --> use the Audit Date column that is first one ex 2026-01-01 so month will be jan-26 like this should be there

mfg qtr --> use the Audit Date column only pick the start date and end date according to that derived the quarter months qtrs. will jan26-apr26 like wise take max year for which we want so simple according date need to derived the quater for the

model ---> use the  Model Code column
MIS ----> use the Pointer column

now when mapped the component we search according the concern for the use the Part Name and Defect Name use this 2 column for failure search other will be same feature like previous count in side table 

for the graphs
vehicle mfg month wise data -----> use the Audit Date column that is first one ex 2026-01-01 so month will be jan-26 like this should be there
reporting months wise data ---> give the attribute bar based on the Attribution column where the data empty take it as unknown
in the KMS wise data ---> give the concern servity bar chart use the Pointer column
in the location graph ----> use the bar chart of the which will use the column Location Name


for the 
RFI:

i will what data you will use so for the filters we have 4 filters
mfg months --> use the Date column that is first one ex 2026-01-01 so month will be jan-26 like this should be there

mfg qtr --> use the Date column only pick the start date and end date according to that derived the quarter months qtrs. will jan26-apr26 like wise take max year for which we want so simple according date need to derived the quater for the

model ---> use the  Model Name column
MIS ----> use the Severity Name column

now when mapped the component we search according the concern for the use the Part Name and Defect Name use this 2 column for failure search other will be same feature like previous count in side table

for the graphs
vehicle mfg month wise data -----> use the Date column that is first one ex 2026-01-01 so month will be jan-26 like this should be there
reporting months wise data ---> give the attribute bar based on the Attribution Name column where the data empty take it as unknown
in the KMS wise data ---> give joint bar graph which will use this 2 column DefectType Name and Severity Name
in the location graph ----> use the bar chart of the which will use the column Area Name


for the
e-SQA:

i will what data you will use so for the filters we have 4 filters
mfg months --> use the Concern Report Date column that is first one ex 2026-01-01 so month will be jan-26 like this should be there

mfg qtr --> use the Concern Report Date column only pick the start date and end date according to that derived the quarter months qtrs. will jan26-apr26 like wise take max year for which we want so simple according date need to derived the quater for the

model ---> use the  Vehicle Model column
MIS ----> use the Concern Catergory column

now when mapped the component we search according the concern for the use the Part Name and Concern Description use this 2 column for failure search other will be same feature like previous count in side table

for the graphs
vehicle mfg month wise data -----> use the Concern Report Date column that is first one ex 2026-01-01 so month will be jan-26 like this should be there
reporting months wise data ---> give the  bar based on the Commodity column where the data empty take it as unknown
in the KMS wise data ---> give bar graph which will use this column Concern Source
in the location graph ----> use the bar chart of the which will use the column Concern Severity



Important don miss this detailed for all this feature i give for that i have give you all the csv in excel_part_labeler_csv_top10 folder 

GNOVAC ----> use this GNOVAC_Export.csv
RPT ----> use this Offline_RPT_Export.csv
RFI ----> use this RFI_Export.csv
e-SQA ----> use this e-SQA_Sheet1.csv

first understand primary feature then required feature use proper mapping according to the feature i have described
deeply analyze my current prompt and requirement 