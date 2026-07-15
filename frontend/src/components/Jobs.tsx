import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api";
import { Search, DollarSign, Calendar, Tag, ChevronLeft, ChevronRight, RefreshCw, AlertCircle } from "lucide-react";

export default function Jobs() {
  const [searchTerm, setSearchTerm] = useState("");
  const [minSalary, setMinSalary] = useState("");
  const [page, setPage] = useState(0);
  const limit = 10;

  const { data, error, isLoading } = useQuery({
    queryKey: ["jobs", searchTerm, minSalary, page],
    queryFn: () => {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(page * limit),
        title: searchTerm,
        ...(minSalary ? { min_salary: minSalary } : {}),
      });
      return apiFetch(`/jobs?${params.toString()}`);
    },
    refetchInterval: 10000,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
  };

  const handleClear = () => {
    setSearchTerm("");
    setMinSalary("");
    setPage(0);
  };

  const total = data?.total ?? 0;
  const jobs = data?.jobs ?? [];
  const maxPages = Math.ceil(total / limit);

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">Active Job Openings</h1>
        <p className="text-gray-500 mt-1">Explore and filter scraped and indexed job postings parsed by our local NLP model.</p>
      </div>

      {/* Search & Filter Form */}
      <form onSubmit={handleSearch} className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-col md:flex-row gap-4 items-end">
        <div className="flex-1 space-y-1 w-full">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Search Role / Skill</label>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="e.g. Python, React, Developer..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg w-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        <div className="w-full md:w-48 space-y-1">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Min Salary (USD/ETB)</label>
          <div className="relative">
            <DollarSign className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <input
              type="number"
              placeholder="e.g. 4000"
              value={minSalary}
              onChange={(e) => setMinSalary(e.target.value)}
              className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg w-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        <div className="flex w-full md:w-auto gap-2">
          <button
            type="submit"
            className="flex-1 md:flex-none bg-blue-600 text-white font-semibold px-5 py-2 rounded-lg text-sm hover:bg-blue-700 transition cursor-pointer"
          >
            Apply Filters
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="bg-gray-100 border border-gray-200 hover:bg-gray-200 text-gray-600 font-semibold px-4 py-2 rounded-lg text-sm transition cursor-pointer"
          >
            Clear
          </button>
        </div>
      </form>

      {/* Jobs Listing */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <RefreshCw className="animate-spin text-blue-600 w-10 h-10" />
          <span className="text-gray-500 font-medium">Filtering job openings...</span>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 text-red-700 p-6 rounded-lg flex items-start space-x-3">
          <AlertCircle className="w-6 h-6 flex-shrink-0" />
          <div>
            <h4 className="font-semibold text-lg">Error fetching jobs</h4>
            <p className="mt-1 text-sm">{(error as Error).message || "An error occurred."}</p>
          </div>
        </div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-16 bg-white border border-gray-100 rounded-xl shadow-sm text-gray-500">
          <Search className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-lg font-medium text-gray-700">No jobs found matching your criteria</p>
          <p className="text-sm text-gray-400 mt-1">Try broadening your search term or lowering your minimum salary threshold.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            {jobs.map((job: any) => {
              let skills = [];
              try {
                skills = JSON.parse(job.skills_required || "[]");
              } catch {
                skills = [];
              }
              return (
                <div
                  key={job.id}
                  className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition duration-150 space-y-4"
                >
                  <div className="flex justify-between items-start">
                    <div className="space-y-1">
                      <h3 className="text-xl font-bold text-gray-900">{job.job_title}</h3>
                      <p className="text-blue-600 font-semibold text-sm">{job.company}</p>
                    </div>
                    {job.salary_range ? (
                      <span className="bg-emerald-50 text-emerald-700 text-sm font-semibold px-3 py-1.5 rounded-full border border-emerald-100">
                        {job.salary_range}
                      </span>
                    ) : (
                      <span className="bg-gray-50 text-gray-500 text-xs font-medium px-2.5 py-1 rounded-full">
                        Salary unspecified
                      </span>
                    )}
                  </div>

                  {skills.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 items-center">
                      <Tag className="w-3.5 h-3.5 text-gray-400 mr-1" />
                      {skills.map((skill: string) => (
                        <span
                          key={skill}
                          className="bg-gray-100 text-gray-700 text-xs font-semibold px-2 py-1 rounded-md"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center text-xs text-gray-400 space-x-1 border-t border-gray-50 pt-3">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Posted on {job.post_date}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination Controls */}
          {maxPages > 1 && (
            <div className="flex justify-between items-center bg-white p-4 rounded-xl border border-gray-100 shadow-sm">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="flex items-center space-x-1 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold px-3 py-1.5 rounded-lg text-sm disabled:opacity-50 transition cursor-pointer"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Previous</span>
              </button>

              <span className="text-sm font-medium text-gray-600">
                Page <span className="font-bold text-gray-900">{page + 1}</span> of <span className="font-bold text-gray-900">{maxPages}</span>
              </span>

              <button
                onClick={() => setPage((p) => Math.min(maxPages - 1, p + 1))}
                disabled={page === maxPages - 1}
                className="flex items-center space-x-1 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold px-3 py-1.5 rounded-lg text-sm disabled:opacity-50 transition cursor-pointer"
              >
                <span>Next</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
